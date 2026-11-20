from datetime import date

from conftest import fixture

from pricecheck.reputation import classify_issue, is_negative, parse_rdap_age, parse_trustpilot


def test_classify_issue_priority_and_accents():
    assert classify_issue("Es una ESTAFA, el envío nunca llegó") == "fraude"      # fraude gana
    assert classify_issue("El paquete no llegó a tiempo") == "entrega"
    assert classify_issue("Sigo esperando el reembolso") == "devolucion"
    assert classify_issue("Vino dañado y no funciona") == "producto"
    assert classify_issue("Atención al cliente pésima") == "atencion"
    assert classify_issue("Me gustó el color") is None


def test_is_negative():
    assert is_negative("Mi pedido no llegó nunca")
    assert not is_negative("Envío rápido y bien embalado")


def test_parse_trustpilot():
    r = parse_trustpilot(fixture("trustpilot.html"), "tiendauno.example")
    assert r.rating == 3.8 and r.review_count == 2500
    assert r.reviews_analyzed == 5
    cats = sorted(i.category for i in r.issues)
    assert cats == ["devolucion", "entrega", "fraude"]          # la de 5★ y la sin problema no cuentan
    assert next(i for i in r.issues if i.category == "entrega").date == date(2026, 10, 2)


def test_rdap_age():
    import json
    data = json.loads(fixture("rdap.json"))
    assert parse_rdap_age(data, today=date(2026, 11, 20)) == (date(2026, 11, 20) - date(2016, 11, 20)).days
    assert parse_rdap_age({"events": []}) is None
