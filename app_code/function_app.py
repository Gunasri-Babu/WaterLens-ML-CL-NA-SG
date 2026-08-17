import azure.functions as func
import pandas as pd
import pickle
import os
import json
import logging
import atexit
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()

# ── environment variables ───────────────────────────────────────
INFLUX_URL      = os.getenv("INFLUXDB_URL")
INFLUX_TOKEN    = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG      = os.getenv("INFLUXDB_ORG")
SRC_BUCKET      = os.getenv("DEVICE_DATA_BUCKET")
SRC_MEASUREMENT = "sensorDataEnriched"
DST_BUCKET      = os.getenv("PREDICTED_BUCKET")
DST_MEASUREMENT = os.getenv("DEVICE_DATA_PREDICTED_MEASUREMENT")

# ── Azure Blob Storage state management ─────────────────────────
STORAGE_CONNECTION = os.getenv("AzureWebJobsStorage")
CONTAINER_NAME     = "function-state"
BLOB_NAME          = "last_processed_time.json"

# ── sensor validation ranges ────────────────────────────────────
VALIDATION_RULES = {
    "pH":           (0.0,     14.0),
    "ORP":          (-1000.0, 1000.0),
    "Conductivity": (0.0,     1000000.0),
}

# ── load pkl artifacts ──────────────────────────────────────────
with open("Chloride_random_forest.pkl", "rb") as f:
    chloride_artifact = pickle.load(f)

with open("Sodium_random_forest.pkl", "rb") as f:
    sodium_artifact = pickle.load(f)

with open("SpecificGravity_random_forest.pkl", "rb") as f:
    specificgravity_artifact = pickle.load(f)

chloride_model        = chloride_artifact["model"]
sodium_model          = sodium_artifact["model"]
specificgravity_model = specificgravity_artifact["model"]
features              = chloride_artifact["features"]  # ['pH', 'ORP', 'Conductivity']

# ── single shared client ────────────────────────────────────────
client    = InfluxDBClient(
    url   = INFLUX_URL,
    token = INFLUX_TOKEN,
    org   = INFLUX_ORG,
)
query_api = client.query_api()
write_api = client.write_api(write_options=SYNCHRONOUS)

atexit.register(lambda: client.close())


# ── blob storage helper ─────────────────────────────────────────

def _get_blob_client():
    service   = BlobServiceClient.from_connection_string(STORAGE_CONNECTION)
    container = service.get_container_client(CONTAINER_NAME)
    try:
        container.create_container()
        logging.info(f"Created blob container: {CONTAINER_NAME}")
    except Exception:
        pass
    return service.get_blob_client(CONTAINER_NAME, BLOB_NAME)


# ── state management functions ──────────────────────────────────

def get_last_processed_time():
    try:
        blob      = _get_blob_client()
        data      = json.loads(blob.download_blob().readall())
        last_time = data.get("last_processed_time")
        logging.info(f"State blob found. Last processed time: {last_time}")
        return last_time
    except Exception:
        logging.info("No state blob found. This is the first run.")
        return None

def save_last_processed_time(timestamp):
    ts          = pd.Timestamp(timestamp)
    ts_plus_1ns = ts + pd.Timedelta(nanoseconds=1)
    iso         = ts_plus_1ns.isoformat()

    blob = _get_blob_client()
    blob.upload_blob(
        json.dumps({"last_processed_time": iso}),
        overwrite=True,
    )
    logging.info(f"State saved. Next run will query from: {iso}")


# ── validation function ─────────────────────────────────────────

def validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    initial_count = len(df)

    df = df.dropna(subset=features)
    nan_dropped = initial_count - len(df)
    if nan_dropped:
        logging.warning(f"Dropped {nan_dropped} rows with NaN values.")

    range_mask = pd.Series(True, index=df.index)
    for col, (lo, hi) in VALIDATION_RULES.items():
        col_mask     = df[col].between(lo, hi)
        out_of_range = (~col_mask).sum()
        if out_of_range:
            logging.warning(
                f"Dropped {out_of_range} rows where {col} is outside "
                f"[{lo}, {hi}]. "
                f"Min={df[col].min():.4f}, Max={df[col].max():.4f}"
            )
        range_mask &= col_mask

    df            = df[range_mask]
    total_dropped = initial_count - len(df)
    logging.info(
        f"Validation complete — kept {len(df)}/{initial_count} rows "
        f"({total_dropped} dropped)."
    )
    return df


# ── helper: predict all three targets ───────────────────────────

def predict_all(X: pd.DataFrame) -> dict:
    return {
        "Chloride"       : chloride_model.predict(X),
        "Sodium"         : sodium_model.predict(X),
        "SpecificGravity": specificgravity_model.predict(X),
    }


# ── main function ───────────────────────────────────────────────

@app.function_name(name="PredictTimer")
@app.schedule(schedule="0 * * * * *", arg_name="myTimer",
              run_on_startup=False,
              use_monitor=True)
def TimerTrigger(myTimer: func.TimerRequest) -> None:

    logging.info("Timer trigger executed.")

    try:
        last_time = get_last_processed_time()

        if last_time:
            range_start = last_time
            logging.info(f"Querying from last saved time: {range_start}")
        else:
            range_start = "-10m"
            logging.info("First run — querying last 10 minutes as default.")

        # ── Query 1: Conductivity (SID filtered, keep DEVICE_NAME + PAD) ──
        flux_query_cond = f"""
        from(bucket: "{SRC_BUCKET}")
          |> range(start: {range_start})
          |> filter(fn: (r) => r["_measurement"] == "{SRC_MEASUREMENT}")
          |> filter(fn: (r) => r["SID"] == "sensorSensorex3020" or r["SID"] == "sensorST726")
          |> filter(fn: (r) => r["_field"] == "Conductivity")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> keep(columns: ["_time", "Conductivity", "DEVICE_NAME", "PAD", "SID"])
        """

        # ── Query 2: pH and ORP (keep DEVICE_NAME for merge key) ──────────
        flux_query_ph = f"""
        from(bucket: "{SRC_BUCKET}")
          |> range(start: {range_start})
          |> filter(fn: (r) => r["_measurement"] == "{SRC_MEASUREMENT}")
          |> filter(fn: (r) => r["_field"] == "pH" or r["_field"] == "ORP")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> keep(columns: ["_time", "pH", "ORP", "DEVICE_NAME"])
        """
        logging.info(f"CONFIG CHECK — URL={INFLUX_URL} | ORG={INFLUX_ORG} | SRC_BUCKET={SRC_BUCKET} | SRC_MEASUREMENT={SRC_MEASUREMENT} | DST_BUCKET={DST_BUCKET}")
        # ── Fetch Conductivity ────────────────────────────────────
        tables_cond  = query_api.query(flux_query_cond)
        records_cond = [r.values for t in tables_cond for r in t.records]
        logging.info(f"Conductivity records fetched: {len(records_cond)}")

        # ── Fetch pH and ORP ──────────────────────────────────────
        tables_ph  = query_api.query(flux_query_ph)
        records_ph = [r.values for t in tables_ph for r in t.records]
        logging.info(f"pH + ORP records fetched: {len(records_ph)}")

        if not records_cond:
            logging.info(
                "No Conductivity records found for sensorSensorex3020 or sensorST726. "
                f"Will retry at next run from same start: {range_start}"
            )
            return

        if not records_ph:
            logging.info(
                "No pH/ORP records found. "
                f"Will retry at next run from same start: {range_start}"
            )
            return

        # ── Build DataFrames ──────────────────────────────────────
        # Conductivity: PAD/SID/DEVICE_NAME may be absent for some devices
        # Fill missing tag columns with NaN rather than crashing
        df_cond_raw = pd.DataFrame(records_cond)

        for col in ["PAD", "SID", "DEVICE_NAME"]:
            if col not in df_cond_raw.columns:
                logging.warning(f"{col} column not found in Conductivity results — filling with NaN.")
                df_cond_raw[col] = pd.NA

         # ── Prioritize Sensorex over ST726 per device+time ──────────
        SID_PRIORITY = {"sensorSensorex3020": 0, "sensorST726": 1}
        df_cond_raw["_sid_rank"] = df_cond_raw["SID"].map(SID_PRIORITY).fillna(99)

        df_cond_raw = ( df_cond_raw
              .sort_values("_sid_rank")
              .drop_duplicates(subset=["_time", "DEVICE_NAME"], keep="first")
              .drop(columns=["_sid_rank"]))

        logging.info(
           f"Conductivity after SID priority dedup: {len(df_cond_raw)} rows "
           f"(Sensorex preferred over ST726)")

        df_cond = df_cond_raw[["_time", "Conductivity", "DEVICE_NAME", "PAD", "SID"]]

        # pH/ORP: DEVICE_NAME only (used as merge key)
        df_ph_orp = pd.DataFrame(records_ph)[["_time", "pH", "ORP", "DEVICE_NAME"]]

        logging.info(f"Conductivity rows : {len(df_cond)}")
        logging.info(f"pH + ORP rows     : {len(df_ph_orp)}")

        # ── Merge on BOTH _time AND DEVICE_NAME ───────────────────
        # This prevents cross-device contamination when timestamps overlap
        df = pd.merge(df_cond, df_ph_orp, on=["_time", "DEVICE_NAME"], how="inner")
        logging.info(f"Rows after merge  : {len(df)}")

        if df.empty:
            logging.info("No matching timestamps after merge. Will retry next run.")
            return

        # ── Validate ──────────────────────────────────────────────
        df = validate_dataframe(df)

        if df.empty:
            logging.warning(
                "All rows removed during validation. "
                "Check sensor health or adjust VALIDATION_RULES."
            )
            return

        # ── Build three feature sets ──────────────────────────────
        X_actual = df[features].copy()

        X_p3 = df[features].copy()
        X_p3["Conductivity"] = X_p3["Conductivity"] * 1.13   # +13%
        X_p3["pH"]           = X_p3["pH"]           * 1.01   # +1%
        X_p3["ORP"]          = X_p3["ORP"]          * 1.01   # +1%

        X_n3 = df[features].copy()
        X_n3["Conductivity"] = X_n3["Conductivity"] * 0.87   # -13%
        X_n3["pH"]           = X_n3["pH"]           * 0.99   # -1%
        X_n3["ORP"]          = X_n3["ORP"]          * 0.99   # -1%

        logging.info(f"X shape: {X_actual.shape}")

        # ── Predict for all three scenarios ───────────────────────
        preds_actual = predict_all(X_actual)
        preds_p3     = predict_all(X_p3)
        preds_n3     = predict_all(X_n3)

        logging.info("Predictions generated for actual, +13%/+1%/+1%, -13%/-1%/-1%.")

        # ── Write to InfluxDB ─────────────────────────────────────
        points = []
        for i, (_, row) in enumerate(df.iterrows()):

            point = (
                Point(DST_MEASUREMENT)
                .time(row["_time"], WritePrecision.NS)
                .tag("SID", row["SID"])

                # actual predictions
                .field("Predicted_Chloride",           float(preds_actual["Chloride"][i]))
                .field("Predicted_Sodium",             float(preds_actual["Sodium"][i]))
                .field("Predicted_SpecificGravity",    float(preds_actual["SpecificGravity"][i]))

                # +13%/+1%/+1% predictions
                .field("Predicted_Chloride_p3",        float(preds_p3["Chloride"][i]))
                .field("Predicted_Sodium_p3",          float(preds_p3["Sodium"][i]))
                .field("Predicted_SpecificGravity_p3", float(preds_p3["SpecificGravity"][i]))

                # -13%/-1%/-1% predictions
                .field("Predicted_Chloride_n3",        float(preds_n3["Chloride"][i]))
                .field("Predicted_Sodium_n3",          float(preds_n3["Sodium"][i]))
                .field("Predicted_SpecificGravity_n3", float(preds_n3["SpecificGravity"][i]))
            )

            # ── Conditionally add DEVICE_NAME and PAD tags ────────
            # Tags are omitted (not set to UNKNOWN) if missing,
            # so WL_7 (no PAD) still gets written cleanly
            if pd.notna(row.get("DEVICE_NAME")):
                point = point.tag("DEVICE_NAME", str(row["DEVICE_NAME"]))
            else:
                logging.warning(f"Row {i} at {row['_time']} has no DEVICE_NAME — tag omitted.")

            if pd.notna(row.get("PAD")):
                point = point.tag("PAD", str(row["PAD"]))
            else:
                logging.warning(f"Row {i} at {row['_time']} (device={row.get('DEVICE_NAME', 'N/A')}) has no PAD — tag omitted.")

            points.append(point)

        write_api.write(
            bucket = DST_BUCKET,
            org    = INFLUX_ORG,
            record = points,
        )

        logging.info(f"Written {len(points)} points to destination bucket.")

        # ── Save state ────────────────────────────────────────────
        latest_ts = df["_time"].max()
        save_last_processed_time(latest_ts)

    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)