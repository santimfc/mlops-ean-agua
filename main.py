# API FastAPI que recibe el historial de un municipio y consulta el endpoint AGUA_IRCA de Databricks
import os
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Credenciales: se inyectan como variables de entorno en Azure (nunca escritas en el código)
DATABRICKS_URL = os.getenv("DATABRICKS_URL")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")

app = FastAPI(
    title="API Calidad del Agua (IRCA)",
    description="Predice si el agua de un municipio será apta para consumo humano (IRCA ≤ 5) el próximo año",
)

# Permite que el frontend (index.html) llame a la API desde otro dominio
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# Campos que espera el modelo (deben coincidir con FEATURES de NB02 y la firma registrada en MLflow)
# Optional = el dato puede faltar (ND en el dataset); el imputer del modelo lo rellena
class Municipio(BaseModel):
    irca_prev: float = Field(..., ge=0, le=100, description="IRCA del año anterior")
    irca_prom_3a: float = Field(..., ge=0, le=100, description="Promedio IRCA de los 3 años anteriores")
    irca_tendencia_3a: Optional[float] = Field(None, ge=-100, le=100, description="IRCA año anterior − IRCA de hace 3 años")
    anios_aptos_prev_3a: float = Field(..., ge=0, le=3, description="Años con agua apta en los últimos 3")
    riesgo_cronico: int = Field(..., ge=0, le=1, description="1 = 3 años seguidos con IRCA > 35")
    ircaurbano_prev: Optional[float] = Field(None, ge=0, le=100, description="IRCA urbano del año anterior")
    ircarural_prev: Optional[float] = Field(None, ge=0, le=100, description="IRCA rural del año anterior")
    tiene_dato_rural_prev: int = Field(..., ge=0, le=1, description="1 = hubo dato rural el año anterior")
    brecha_urb_rur_prev: Optional[float] = Field(None, ge=-100, le=100, description="IRCA rural − IRCA urbano (año anterior)")
    irca_dep_mediana: float = Field(..., ge=0, le=100, description="Mediana IRCA del departamento (año anterior)")
    post_2020: int = Field(..., ge=0, le=1, description="1 = año 2020 en adelante")

    # Ejemplo real de la tabla oro (Medellín 2024) para probar desde /docs
    model_config = {"json_schema_extra": {"example": {
        "irca_prev": 1.5, "irca_prom_3a": 2.3, "irca_tendencia_3a": -1.0,
        "anios_aptos_prev_3a": 3.0, "riesgo_cronico": 0,
        "ircaurbano_prev": 1.1, "ircarural_prev": 2.9, "tiene_dato_rural_prev": 1,
        "brecha_urb_rur_prev": 1.8, "irca_dep_mediana": 2.4, "post_2020": 1,
    }}}


@app.get("/health")
def health():
    # Verifica que la API está viva y que tiene configuradas las credenciales
    return {"status": "ok", "databricks_configurado": bool(DATABRICKS_URL and DATABRICKS_TOKEN)}


@app.post("/predecir")
def predecir(mun: Municipio):
    if not (DATABRICKS_URL and DATABRICKS_TOKEN):
        raise HTTPException(status_code=500, detail="Faltan DATABRICKS_URL o DATABRICKS_TOKEN")

    # Databricks exige el formato dataframe_records (los None viajan como null)
    payload = {"dataframe_records": [mun.model_dump()]}

    try:
        r = requests.post(
            DATABRICKS_URL,
            headers={"Authorization": f"Bearer {DATABRICKS_TOKEN}"},
            json=payload,
            timeout=120,  # margen para el arranque en frío del endpoint
        )
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Databricks tardó demasiado (arranque en frío). Intente de nuevo.")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Error de Databricks: {r.text}")

    pred = int(r.json()["predictions"][0])  # 1 = agua apta, 0 = con riesgo
    return {
        "prediccion": pred,
        "resultado": "Agua apta para consumo ✅" if pred == 1 else "Agua con riesgo ⚠️",
        "datos_recibidos": mun.model_dump(),
    }
