"""Reduce el dataset Flight Prices de Expedia (~31 GB) a una muestra manejable.

Lee el zip por partes, sin descomprimirlo a disco, y conserva un porcentaje de
los vuelos con TODAS sus consultas, para no romper el historial de precios.

La muestra es reproducible sin semilla: un vuelo entra segun su legId, que ya
es un hash MD5, asi que la seleccion siempre es la misma.

Uso: python reducir_dataset.py data/expedia_full/flightprices.zip salida.csv.gz 10
"""
import subprocess
import sys

import pandas as pd

COLUMNAS = [
    "legId", "searchDate", "flightDate", "startingAirport", "destinationAirport",
    "travelDuration", "isBasicEconomy", "isNonStop", "totalFare", "seatsRemaining",
    "totalTravelDistance", "segmentsDepartureTimeRaw", "segmentsAirlineName",
]


def reducir_bloque(bloque, porcentaje):
    # Los primeros 8 digitos hexadecimales del hash se distribuyen uniformemente.
    elegido = bloque["legId"].str[:8].map(lambda h: int(h, 16) % 100 < porcentaje)
    b = bloque[elegido].copy()

    duracion = b["travelDuration"].str.extract(r"PT(?:(\d+)H)?(?:(\d+)M)?").astype(float).fillna(0)
    b["duracion_min"] = duracion[0] * 60 + duracion[1]
    b["hora_salida"] = b["segmentsDepartureTimeRaw"].str[11:13].astype(int)
    b["aerolinea"] = b["segmentsAirlineName"].str.split("||", regex=False).str[0]
    b["segmentos"] = b["segmentsAirlineName"].str.count(r"\|\|") + 1
    return b.drop(columns=["travelDuration", "segmentsDepartureTimeRaw", "segmentsAirlineName"])


def main(zip_path, salida, porcentaje):
    # unzip -p transmite el CSV; tambien soporta Deflate64, que zipfile no lee.
    proceso = subprocess.Popen(["unzip", "-p", zip_path, "itineraries.csv"], stdout=subprocess.PIPE)
    partes, leidas = [], 0
    for bloque in pd.read_csv(proceso.stdout, usecols=COLUMNAS, chunksize=2_000_000, low_memory=False):
        leidas += len(bloque)
        partes.append(reducir_bloque(bloque, porcentaje))
        print(f"filas leidas: {leidas:,}", flush=True)
    if proceso.wait() != 0:
        raise SystemExit("unzip termino con error; la lectura quedo incompleta")

    df = pd.concat(partes, ignore_index=True)
    print(f"filas de los vuelos elegidos: {len(df):,}", flush=True)

    # Casi siempre hay una fila por vuelo y consulta. En los pocos duplicados
    # se conserva la mas barata, que es el precio que veria el comprador.
    df = df.sort_values("totalFare").drop_duplicates(["legId", "searchDate"])
    df = df.sort_values(["flightDate", "legId", "searchDate"])

    # Un identificador corto pesa mucho menos que el hash de 32 caracteres.
    df["legId"] = pd.factorize(df["legId"])[0]
    df = df.rename(columns={"legId": "vuelo_id"})
    df.to_csv(salida, index=False, compression={"method": "gzip", "compresslevel": 9})
    print(f"filas finales: {len(df):,}, vuelos: {df['vuelo_id'].nunique():,}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
