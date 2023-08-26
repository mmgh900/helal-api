import json
import numpy as np
import pymssql
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request

import codecs

from ai_models.days_open import DaysOpenModel
from ai_models.insemination_res import InseminationResModel

app = FastAPI()
origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:3001",
    "http://localhost:3000",
    "http://192.168.32.1:3001",
    "http://2.180.5.196:3000",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Define a function to create a database connection
def create_connection():
    server = "192.168.101.246\\SQLEXPRESS"
    database = "ModiranFarmer"
    username = "mmgh900"
    password = "0936"
    conn = pymssql.connect(server, username, password, database)

    return conn


days_open_model = DaysOpenModel(create_connection())
insemination_res_model = InseminationResModel(create_connection())





# Read histogram keys and queries from JSON file in Windows-1256 encoding
with codecs.open("histogram_config.json", "r", "UTF-8") as file:
    histogram_config = json.load(file)


# Connect to the database at startup
@app.on_event("startup")
async def startup_event():
    global conn
    conn = create_connection()


def create_histogram(bins: int, query: str):
    cursor = conn.cursor()

    cursor.execute(query)
    rows = cursor.fetchall()

    # Convert the values in the AllMilk column to float, filtering out any None values
    data = [float(row[0]) for row in rows if row[0] is not None and not np.isnan(float(row[0]))]

    # Create histogram bins using NumPy
    hist, bin_edges = np.histogram(data, bins=bins)
    bin_edges = np.ceil(bin_edges)

    # Create a histogram data structure
    histogram = {
        "data": hist.tolist(),
        "bins": bin_edges.tolist()
    }

    return histogram


@app.get("/histograms")
async def get_histogram_names():
    names = [histogram["name"] for histogram in histogram_config]
    return {"histogram_names": names}


@app.get("/histograms/{histogram_key}/params")
async def get_histogram_params(histogram_key: str):
    params = [histogram["parameters"] for histogram in histogram_config if histogram['name'] == histogram_key]
    return {"histogram_parameters": params[0]}


@app.get("/histograms/{histogram_key}")
async def get_histogram(histogram_key: str, request: Request):
    query = ""
    parameters = {}

    for histogram in histogram_config:
        if histogram["name"] == histogram_key:
            query = histogram["queries"]
            parameters = histogram["parameters"]
            break

    if query == "":
        return {"error": "Invalid histogram key"}

    missing_params = [param['title'] for param in parameters if param['title'] not in request.query_params.keys()]
    if missing_params:
        error_message = f"Missing required parameters: {', '.join(missing_params)}"
        return {"error": error_message}

    # Replace query placeholders with actual parameter values
    for param in parameters:
        param_value = request.query_params[param['title']]
        query = query.replace(f"{{{param['title']}}}", str(param_value))

    return create_histogram(int(request.query_params['bins']), query)



@app.post("/models/days-open/retrain")
async def retrain_o():
    global days_open_model
    days_open_model = DaysOpenModel(create_connection(), force_retrain=True)
    return days_open_model.accuracy

@app.post("/models/insemination-result/retrain")
async def retrain_i():
    global insemination_res_model
    insemination_res_model = InseminationResModel(create_connection(), force_retrain=True)
    return insemination_res_model.accuracy


@app.get("/models/days-open")
async def get_milk_production_histogram(serial: str):
    cursor = conn.cursor()

    cursor.execute(f"""
    SELECT s.Serial, s.LastBriding, s.TalghihStatus, s.SickStatus, s.CowKind, m.MilkPeriod, m.IsDieEmengercy, s.BodyScore, m.Exist
    FROM [ModiranFarmer].[dbo].[Main] m
    RIGHT OUTER JOIN [ModiranFarmer].[dbo].[CowStatus] s ON m.Serial = s.Serial
    WHERE m.Serial = '{serial}'
    ORDER BY m.MilkPeriod DESC
    """)
    rows = cursor.fetchall()
    if len(rows) < 1:
        raise HTTPException(status_code=404, detail="شناسه نامعتبر است. این دام در دیتابیس وجود ندارد.")

    status = str(rows[0][8]).strip()
    # if 'حذف شده' in status:
    #     raise HTTPException(status_code=400, detail="این گاو حدف شده است")

    prediction = days_open_model.predict(serial)
    respond = {"data": {
        "Prediction": str(prediction),
        "LastBriding": rows[0][1],
        "TalghihStatus": rows[0][2],
        "SickStatus": rows[0][3],
        "CowKind": rows[0][4],
        "MilkPeriod": rows[0][5],
        "IsDieEmengercy": rows[0][6],
        "BodyScore": rows[0][7],
        "Exist": rows[0][8],

    }}
    return respond


@app.get("/models/insemination-result")
async def get_insemination_result(serial: str, date: str = None, natural_breeding=False):
    cursor = conn.cursor()

    cursor.execute(f"""
    SELECT s.Serial, s.LastBriding, s.TalghihStatus, s.SickStatus, s.CowKind, m.MilkPeriod, m.IsDieEmengercy, s.BodyScore, m.Exist
    FROM [ModiranFarmer].[dbo].[Main] m
    RIGHT OUTER JOIN [ModiranFarmer].[dbo].[CowStatus] s ON m.Serial = s.Serial
    WHERE m.Serial = '{serial}'
    ORDER BY m.MilkPeriod DESC
    """)
    rows = cursor.fetchall()
    if len(rows) < 1:
        raise HTTPException(status_code=404, detail="شناسه نامعتبر است. این دام در دیتابیس وجود ندارد.")

    status = str(rows[0][8]).strip()
    # if 'حذف شده' in status:
    #     raise HTTPException(status_code=400, detail="این گاو حدف شده است")

    prediction = insemination_res_model.predict(serial, date, natural_breeding == 'true')
    respond = {"data": {
        "Prediction": str(prediction[0]),
        "TimeBred": str(prediction[1].CurrentTimesBred[0] + 1),
        "LastBriding": rows[0][1],
        "TalghihStatus": rows[0][2],
        "SickStatus": rows[0][3],
        "CowKind": rows[0][4],
        "MilkPeriod": rows[0][5],
        "IsDieEmengercy": rows[0][6],
        "BodyScore": rows[0][7],
        "Exist": rows[0][8],

    }}
    return respond
