from typing import List

import pymssql
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:3001",
    "http://localhost:3000",
    "http://192.168.32.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Define a function to create a database connection
async def create_connection():
    server = "192.168.32.2\\SQLEXPRESS"
    database = "ModiranFarmer"
    username = "mmgh900"
    password = "0936"
    cnxn = pymssql.connect(server, username, password, database)
    return cnxn


def create_histogram(bins: int, query: str):
    cnxn = create_connection()
    cursor = cnxn.cursor()

    cursor.execute(query)
    rows = cursor.fetchall()

    # Convert the values in the AllMilk column to float, filtering out any None values
    data = [float(row[0]) for row in rows if row[0] is not None and not np.isnan(float(row[0]))]

    # Create histogram bins using NumPy
    hist, bin_edges = np.histogram(data, bins=bins)

    # Create a histogram data structure
    histogram = {
        "data": hist.tolist(),
        "bins": bin_edges.tolist()
    }

    return histogram


@app.get("/histograms/milk-production")
async def get_milk_production_histogram(bins: int = 15):
    query = f"SELECT AllMilk FROM StandardMilk "

    return create_histogram(bins, query)


@app.get("/histograms/calving_age")
async def get_milk_production_histogram(bins: int = 15, calving_number: int = 0):
    query = f"""
            SELECT DATEDIFF(month,  Main.EngBDate, Calving.EngZDate) AS AgeAtCalvingInDays
            FROM [ModiranFarmer].[dbo].[Zayesh] Calving
            JOIN [ModiranFarmer].[dbo].[Main] Main ON Main.Serial = Calving.Serial 
            WHERE Calving.MilkPeriod = {calving_number} AND DATEDIFF(month,  Main.EngBDate, Calving.EngZDate) > 12
        """

    return create_histogram(bins, query)
