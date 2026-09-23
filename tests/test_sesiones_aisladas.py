"""La API no debe mezclar el mapa ni el tablero de distintos navegadores."""

from app import app


def test_cada_cliente_mantiene_su_capitulo_activo():
    anterior = app.config["TESTING"]
    app.config["TESTING"] = False
    try:
        cliente_a = app.test_client()
        cliente_b = app.test_client()

        assert cliente_a.post("/api/mapa/seleccionar", json={"capitulo": 8}).status_code == 200
        assert cliente_a.get("/api/estado").get_json()["mapa"]["capitulo"] == 8
        assert cliente_b.get("/api/estado").get_json()["mapa"]["capitulo"] == 7

        assert cliente_b.post("/api/mapa/seleccionar", json={"capitulo": 9}).status_code == 200
        assert cliente_a.get("/api/estado").get_json()["mapa"]["capitulo"] == 8
        assert cliente_b.get("/api/estado").get_json()["mapa"]["capitulo"] == 9
    finally:
        app.config["TESTING"] = anterior
