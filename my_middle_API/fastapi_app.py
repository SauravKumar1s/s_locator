import uuid
from typing import Awaitable
from typing import Optional, Callable, Any, Type, TypeVar

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

from all_types.myapi_dtypes import ReqApplyZoneLayers, ResApplyZoneLayers
from all_types.myapi_dtypes import (
    ReqLocation,
    ReqCatalogId,
    ResAllCards,
    ResAcknowlg,
    ResTypeMapData,
    ResCountryCityData,
    ResNearbyCategories,
    ResOldNearbyCategories,
    ReqCreateLyr,
    ResCreateLyr,
    ReqSavePrdcerLyer,
    ReqPrdcerLyrMapData,
    ResPrdcerLyrMapData,
    ReqCreateUserProfile,
    ResCreateUserProfile,
    RequestModel
)
from all_types.myapi_dtypes import (
    ReqUserId,
    ResUserLayers,
    ReqSavePrdcerCtlg,
    ResSavePrdcerCtlg,
)
from all_types.myapi_dtypes import ResUserCatalogs, ReqFetchCtlgLyrs, ResCtlgLyrs
from config_factory import get_conf
from data_fetcher import (
    get_boxmap_catlog_data,
    fetch_catlog_collection,
    nearby_boxmap,
    fetch_layer_collection,
    old_fetch_nearby_categories,
    fetch_country_city_category_map_data,
    save_lyr,
    fetch_user_lyrs,
    fetch_lyr_map_data,
    create_save_prdcer_ctlg,
    fetch_prdcer_ctlgs,
    fetch_ctlg_lyrs,
    apply_zone_layers,
    create_user_profile,
)
from storage import fetch_country_city_data, fetch_nearby_categories

CONF = get_conf()

app = FastAPI()

# Enable CORS
origins = [CONF.enable_CORS_url]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, request_id: str):
        await websocket.accept()
        self.active_connections[request_id] = websocket

    def disconnect(self, request_id: str):
        if request_id in self.active_connections:
            del self.active_connections[request_id]

    async def send_personal_message(self, message: str, request_id: str):
        if request_id in self.active_connections:
            await self.active_connections[request_id].send_text(message)

    async def send_json(self, data: dict, request_id: str):
        if request_id in self.active_connections:
            await self.active_connections[request_id].send_json(data)


manager = ConnectionManager()


async def ws_handling(
        websocket: WebSocket,
        request_id: str,
        input_type: Type[BaseModel],
        output_type: Type[BaseModel],
        custom_function: Callable[[Any], Awaitable[Any]],
):
    await manager.connect(websocket, request_id)
    try:
        while True:
            req = await websocket.receive_text()
            parsed_req = input_type.model_validate_json(req)
            response = await custom_function(parsed_req)
            try:
                validated_output = output_type.model_validate(response)
                await manager.send_json(
                    {"data": validated_output.model_dump()}, request_id
                )
            except ValidationError as e:
                error_message = f"Output data validation failed: {str(e)}"
                await manager.send_json({"error": error_message}, request_id)
    except WebSocketDisconnect:
        manager.disconnect(request_id)
        print(f"WebSocket disconnected: {request_id}")


T = TypeVar('T', bound=BaseModel)
U = TypeVar('U', bound=BaseModel)


async def http_handling(
        req: Optional[T],
        input_type: Optional[Type[T]],
        output_type: Type[U],
        custom_function: Optional[Callable[..., Awaitable[Any]]],
):
    output = ""


    if req is not None:
        req = req.request_body
        try:
            input_type.model_validate(req)
        except ValidationError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid request body with error: {e}"
            ) from e

    if custom_function is not None:
        output = await custom_function(req=req)

    request_id = "req-" + str(uuid.uuid4())

    res_body = output_type(
        message="Request received",
        request_id=request_id,
        data=output,
    )

    return res_body


@app.post(CONF.http_catlog_data, response_model=ResTypeMapData)
async def catlog_data(catlog_req: RequestModel[ReqCatalogId]):
    response = await http_handling(
        catlog_req,
        ReqCatalogId,
        ResTypeMapData,
        get_boxmap_catlog_data,
    )
    return response


@app.post(CONF.http_single_nearby, response_model=ResTypeMapData)
async def single_nearby(req: RequestModel[ReqLocation]):
    response = await http_handling(
        req,
        ReqLocation,
        ResTypeMapData,
        nearby_boxmap,
    )
    return response


@app.get(CONF.fetch_acknowlg_id, response_model=ResAcknowlg)
async def fetch_acknowlg_id():
    response = await http_handling(
        None,
        None,
        ResAcknowlg,
        None,
    )
    return response


@app.get(CONF.catlog_collection, response_model=ResAllCards)
async def catlog_collection():
    response = await http_handling(
        None,
        None,
        ResAllCards,
        fetch_catlog_collection,
    )
    return response


@app.get(CONF.layer_collection, response_model=ResAllCards)
async def layer_collection():
    response = await http_handling(
        None,
        None,
        ResAllCards,
        fetch_layer_collection,
    )
    return response


@app.get(CONF.country_city, response_model=ResCountryCityData)
async def country_city():
    response = await http_handling(
        None,
        None,
        ResCountryCityData,
        fetch_country_city_data,
    )
    return response


@app.get(CONF.nearby_categories, response_model=ResNearbyCategories)
async def nearby_categories():
    response = await http_handling(
        None,
        None,
        ResNearbyCategories,
        fetch_nearby_categories,
    )
    return response


@app.get(CONF.old_nearby_categories, response_model=ResOldNearbyCategories)
async def old_nearby_categories():
    response = await http_handling(
        None,
        None,
        ResOldNearbyCategories,
        old_fetch_nearby_categories,
    )
    return response


@app.post(CONF.create_layer, response_model=ResCreateLyr)
async def create_layer(req: RequestModel[ReqCreateLyr]):
    response = await http_handling(
        req,
        ReqCreateLyr,
        ResCreateLyr,
        fetch_country_city_category_map_data,
    )
    return response


@app.post(CONF.save_producer_layer, response_model=ResAcknowlg)
async def save_producer_layer(req: RequestModel[ReqSavePrdcerLyer]):
    response = await http_handling(
        req,
        ReqSavePrdcerLyer,
        ResAcknowlg,
        save_lyr,
    )
    return response


@app.post(CONF.user_layers, response_model=ResUserLayers)
async def user_layers(req: RequestModel[ReqUserId]):
    response = await http_handling(
        req, ReqUserId, ResUserLayers, fetch_user_lyrs
    )
    return response


@app.post(CONF.prdcer_lyr_map_data, response_model=ResPrdcerLyrMapData)
async def prdcer_lyr_map_data(req: RequestModel[ReqPrdcerLyrMapData]):
    response = await http_handling(
        req, ReqPrdcerLyrMapData, ResPrdcerLyrMapData, fetch_lyr_map_data
    )
    return response


@app.post(CONF.save_producer_catalog, response_model=ResSavePrdcerCtlg)
async def save_producer_catalog(req: RequestModel[ReqSavePrdcerCtlg]):
    response = await http_handling(
        req,
        ReqSavePrdcerCtlg,
        ResSavePrdcerCtlg,
        create_save_prdcer_ctlg,
    )
    return response


@app.post(CONF.user_catalogs, response_model=ResUserCatalogs)
async def user_catalogs(req: RequestModel[ReqUserId]):
    response = await http_handling(
        req, ReqUserId, ResUserCatalogs, fetch_prdcer_ctlgs
    )
    return response


@app.post(CONF.fetch_ctlg_lyrs, response_model=ResCtlgLyrs)
async def fetch_catalog_layers(req: RequestModel[ReqFetchCtlgLyrs]):
    response = await http_handling(req, ReqFetchCtlgLyrs, ResCtlgLyrs, fetch_ctlg_lyrs)
    return response


@app.post(CONF.apply_zone_layers, response_model=ResApplyZoneLayers)
async def apply_zone_layers_endpoint(req: RequestModel[ReqApplyZoneLayers]):
    response = await http_handling(
        req, ReqApplyZoneLayers, ResApplyZoneLayers, apply_zone_layers
    )
    return response


@app.post(CONF.create_user_profile, response_model=ResCreateUserProfile)
async def create_user_profile_endpoint(req: RequestModel[ReqCreateUserProfile]):
    response = await http_handling(
        req, ReqCreateUserProfile, ResCreateUserProfile, create_user_profile
    )
    return response
