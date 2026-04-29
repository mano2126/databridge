from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.api.routes import connector, jobs, schema, mapping, validate, report, settings, sql_converter, obj_mapping, obj_mapping
from app.websocket.ws_router import ws_router
import traceback
import re


# ── pyodbc 전역 패치 ──────────────────────────────────────
def _patch_pyodbc():
    try:
        import pyodbc as _pyodbc
        _original_connect = _pyodbc.connect

        def _patched_connect(connstring, *args, **kwargs):
            s = str(connstring)

            if 'SQL Server' in s:
                # Encrypt 속성 제거
                s = re.sub(r';?Encrypt=[^;]+', '', s)

                # 잘못된 속성 제거
                s = re.sub(r';?Connection Timeout=\d+', '', s)

                # TrustServerCertificate=yes 추가
                if 'TrustServerCertificate' not in s:
                    s = s.rstrip(';') + ';TrustServerCertificate=yes;'

                # ODBC Driver 17 → 18 자동 교체
                available = _pyodbc.drivers()
                if 'ODBC Driver 17 for SQL Server' in s and \
                   'ODBC Driver 17 for SQL Server' not in available and \
                   'ODBC Driver 18 for SQL Server' in available:
                    s = s.replace('ODBC Driver 17 for SQL Server',
                                  'ODBC Driver 18 for SQL Server')

                # timeout 키워드 인수 제거
                # (커넥터 테스트는 timeout kwarg 없이 성공 — 동일하게 맞춤)
                kwargs.pop('timeout', None)

            print(f'[PYODBC] → {s} | kwargs={kwargs}', flush=True)
            return _original_connect(s, *args, **kwargs)

        _pyodbc.connect = _patched_connect
        print('[DataBridge] pyodbc 패치 완료', flush=True)
    except ImportError:
        print('[DataBridge] pyodbc 없음', flush=True)


_patch_pyodbc()
# ─────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="DataBridge Studio API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f'\n[ERROR] {request.url}\n{tb}', flush=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )


P = "/api/v1"
app.include_router(connector.router,     prefix=f"{P}/connectors",    tags=["Connector"])
app.include_router(jobs.router,          prefix=f"{P}/jobs",          tags=["Jobs"])
app.include_router(schema.router,        prefix=f"{P}/schema",        tags=["Schema"])
app.include_router(mapping.router,       prefix=f"{P}/mapping",       tags=["Mapping"])
app.include_router(validate.router,      prefix=f"{P}/validate",      tags=["Validate"])
app.include_router(report.router,        prefix=f"{P}/report",        tags=["Report"])
app.include_router(settings.router,      prefix=f"{P}/settings",      tags=["Settings"])
app.include_router(sql_converter.router, prefix=f"{P}/sql-converter", tags=["SQL Converter"])
app.include_router(obj_mapping.router,  prefix=f"{P}/obj-mapping",   tags=["ObjectMapping"])
app.include_router(obj_mapping.router,  prefix=f"{P}/obj-mapping",   tags=["ObjectMapping"])
app.include_router(ws_router, prefix="/ws")


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
