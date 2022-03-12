"""Do your Data Science here."""

import sqlite3
import pandas as pd
import numpy as np
import datetime as dt

# pandas controls on how much data to see
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)


def execute_triangle_arbitrage():
    """Execute Triangle Arbitrage."""
    con = sqlite3.connect("db/kucoin.db")
    cur = con.cursor()
    df = pd.read_sql_query("SELECT * FROM tickers", con)
    df = df.astype(
        {
            "baseTick": "str",
            "quoteTick": "str",
            "bestAsk": "float",
            "bestAskSize": "float",
            "bestBid": "float",
            "bestBidSize": "float",
            "price": "float",
            "sequence": "float",
            "size": "float",
            "time": "str",
        }
    )
    df["time"] = pd.to_datetime(df["time"], infer_datetime_format=True)
    df = df.sort_values("time").drop_duplicates(["baseTick", "quoteTick"], keep="last")
    df.reset_index(drop=True, inplace=True)
    df.sort_values("baseTick", inplace=True)
    df.to_csv("market.csv", index=False)

    combo = [
        [a, b, c]
        for a in df["quoteTick"].unique()
        for b in df["baseTick"].unique()
        for c in df["quoteTick"].unique()
    ]
    arb_op = pd.DataFrame(combo, columns=["a", "b", "c"], dtype=str)

    arb_op.reset_index(drop=True, inplace=True)

    arb_op.rename(columns={"b": "baseTick", "a": "quoteTick"}, inplace=True)

    arb_op["ba_bstb"] = arb_op.merge(
        df,
        on=["baseTick", "quoteTick"],
        how="left",
    )["bestBid"]

    arb_op["ba_bsta"] = arb_op.merge(
        df,
        on=["baseTick", "quoteTick"],
        how="left",
    )["bestAsk"]

    arb_op.rename(columns={"baseTick": "b", "quoteTick": "a"}, inplace=True)
    arb_op.rename(columns={"b": "baseTick", "c": "quoteTick"}, inplace=True)
    arb_op["bc_bstb"] = arb_op.merge(
        df,
        on=["baseTick", "quoteTick"],
        how="left",
    )["bestBid"]

    arb_op["bc_bsta"] = arb_op.merge(
        df,
        on=["baseTick", "quoteTick"],
        how="left",
    )["bestAsk"]

    arb_op.rename(columns={"baseTick": "b", "quoteTick": "c"}, inplace=True)

    arb_op.rename(columns={"c": "baseTick", "a": "quoteTick"}, inplace=True)
    arb_op["ca_bstb"] = arb_op.merge(
        df,
        on=["baseTick", "quoteTick"],
        how="left",
    )["bestBid"]

    arb_op["ca_bsta"] = arb_op.merge(
        df,
        on=["baseTick", "quoteTick"],
        how="left",
    )["bestAsk"]

    arb_op.rename(columns={"baseTick": "c", "quoteTick": "a"}, inplace=True)

    arb_op.dropna(inplace=True)

    arb_op["fwd_arb"] = (
        (arb_op["ba_bstb"] * 1.001)
        * (1 / (arb_op["bc_bsta"] * 1.001))
        * (1 / (arb_op["ca_bsta"] * 1.001))
        - 1
    ) * 100
    arb_op["rev_arb"] = (
        arb_op["bc_bstb"]
        * 1.001
        * arb_op["ca_bstb"]
        * 1.001
        * (1 / (arb_op["ba_bsta"] * 1.001))
        - 1
    ) * 100

    arb_op.loc[~(arb_op["fwd_arb"] > 0.1), "fwd_arb"] = np.nan
    arb_op.loc[~(arb_op["rev_arb"] > 0.1), "rev_arb"] = np.nan
    arb_op = arb_op.loc[arb_op[["fwd_arb", "rev_arb"]].idxmax()]
    arb_op.dropna(subset=["fwd_arb", "rev_arb"], how="all", inplace=True)
    arb_op.drop_duplicates(inplace=True)
    table = "arb_ops"
    create_table = """CREATE TABLE IF NOT EXISTS arb_ops
                    (a text, b text,  c text, ba_bstb text, ba_bsta text, bc_bstb text, bc_bsta text, ca_bstb text, ca_bsta text, fwd_arb text, rev_arb text, UNIQUE (fwd_arb, rev_arb) ON CONFLICT IGNORE
                    )"""
    print("Creating Table arb_ops")
    cur.execute(create_table)
    con.commit()
    for i, row in arb_op.iterrows():
        placeholders = ",".join('"' + str(e) + '"' for e in row)
        columns = ", ".join(arb_op.columns)
        insert_table = "INSERT INTO %s ( %s ) VALUES ( %s )" % (
            table,
            columns,
            placeholders,
        )
        print("Inserting a row of data")
        cur.execute(insert_table)
        con.commit()
    con.close()
    arb_op.to_csv("arbitrage_ops.csv", index=False)
