import httpx


GIS_BASE = (
    "https://gis.charleston-sc.gov/arcgis2/rest/services/External/"
    "RoadClosuresViewer/MapServer"
)


def test_road_impacts_combine_selected_layers_and_omit_line_coordinates(
    client_factory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        layer_id = request.url.path.split("/")[-2]
        assert request.url.path.startswith("/arcgis2/rest/services/External/")
        params = dict(request.url.params)
        assert params["where"] == "STATUS = 'ACTIVE'"
        assert params["outSR"] == "4326"
        assert params["returnGeometry"] == "true"
        assert params["f"] == "json"
        if layer_id in ("1", "5"):
            assert "STREET" in params["outFields"]
            attributes = {
                "OBJECTID": 700 + int(layer_id),
                "STREET": "King St",
                "LOCATION": "At Market St",
                "TYPE": "CLOSED",
                "REASON": "FLOOD",
                "STATUS": "ACTIVE",
                "START": 1790942400000,
                "END_": None,
            }
        else:
            assert layer_id == "2"
            assert "BLOCKNM" in params["outFields"]
            attributes = {
                "OBJECTID": 42,
                "BLOCKNM": "Meeting St",
                "COMMENT": "Detour in effect",
                "STATUS": "ACTIVE",
                "STARTDATE": 1790942400000,
                "ENDDATE": None,
            }
        return httpx.Response(
            200,
            json={
                "spatialReference": {"wkid": 4326},
                "features": [
                    {
                        "attributes": attributes,
                        "geometry": {"paths": [[[-79.9, 32.8], [-79.8, 32.9]]]},
                    }
                ],
            },
        )

    response = client_factory(handler).get("/api/roads/impacts")

    assert response.status_code == 200
    impacts = response.json()
    assert len(impacts) == 3
    assert {impact["source_layer"] for impact in impacts} == {
        "ROAD CLOSURE (1)",
        "ROAD CLOSURE EM (5)",
        "DETOURS (2)",
    }
    closure = next(impact for impact in impacts if impact["source_layer"] == "ROAD CLOSURE (1)")
    assert closure["road_name"] == "King St"
    assert closure["reason"] == "FLOOD"
    assert closure["latitude"] is None
    assert closure["longitude"] is None
    assert closure["source"] == GIS_BASE


def test_no_current_road_impacts_returns_empty_list(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"features": []})

    response = client_factory(handler).get("/api/roads/impacts")

    assert response.status_code == 200
    assert response.json() == []


def test_gis_fetches_next_page_when_transfer_limit_is_exceeded(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        layer_id = request.url.path.split("/")[-2]
        offset = dict(request.url.params)["resultOffset"]
        if layer_id == "1":
            if offset == "0":
                return httpx.Response(
                    200,
                    json={
                        "features": [{"attributes": {"OBJECTID": 10}}],
                        "exceededTransferLimit": True,
                    },
                )
            assert offset == "1"
            return httpx.Response(
                200,
                json={"features": [{"attributes": {"OBJECTID": 11}}]},
            )
        return httpx.Response(200, json={"features": []})

    response = client_factory(handler).get("/api/roads/impacts")

    assert response.status_code == 200
    assert [impact["id"] for impact in response.json()] == ["1:10", "1:11"]


def test_gis_upstream_failure_is_sanitized(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="private GIS server detail")

    response = client_factory(handler).get("/api/roads/impacts")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Unable to retrieve road-impact data from Charleston GIS."
    }
    assert "private GIS server detail" not in response.text