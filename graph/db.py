"""Neo4j driver helper. `python -m graph.db` pings the server and prints its version."""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase, RoutingControl

load_dotenv()


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    """Return a cached driver built from .env."""
    return GraphDatabase.driver(os.environ["NEO4J_URI"],
                                auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))


def database() -> str:
    return os.environ.get("NEO4J_DATABASE", "neo4j")


def read(query: str, **params) -> list[dict]:
    """Run a parameterised read query and return records as dicts."""
    records, _, _ = get_driver().execute_query(query, params, database_=database(), routing_=RoutingControl.READ)
    return [r.data() for r in records]


def write(query: str, **params) -> list[dict]:
    """Run a parameterised write query and return records as dicts."""
    records, _, _ = get_driver().execute_query(query, params, database_=database())
    return [r.data() for r in records]


if __name__ == "__main__":
    d = get_driver()
    d.verify_connectivity()
    info = read("CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition")
    print(info)
