# "api.py" from NUSGet-Web-Backend by NinjaCheetah
# https://github.com/NinjaCheetah/NUSGet-Web-Backend

from importlib.metadata import version
import io
import json
import zipfile

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import libWiiPy
import libTWLPy


class TitleNotFoundException(Exception):
    def __init__(self, tid: str):
        self.tid = tid

class NoTicketException(Exception):
    def __init__(self, tid: str):
        self.tid = tid

app = FastAPI()
origins = [
    "http://localhost:4000",
    "http://127.0.0.1:4000",
    "https://nusget.ninjacheetah.dev",
]
# noinspection PyTypeChecker
# PyCharm thinks CORSMiddleware is the wrong type, it's a confirmed PyCharm bug.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(TitleNotFoundException)
def title_not_found_exception_handler(request: Request, exc: TitleNotFoundException):
    return JSONResponse(
        status_code=404,
        content={
            "message": f"Title ID {exc.tid} or Title version not found.",
            "code": "title.notfound",
            "image": "https://http.cat/404"
        },
    )

@app.exception_handler(NoTicketException)
def no_ticket_exception_handler(request: Request, exc: NoTicketException):
    return JSONResponse(
        status_code=406,
        content={
            "message": f"No Ticket is available for the requested Title {exc.tid}.",
            "code": "title.notik",
            "image": "https://http.cat/406"
        },
    )

@app.get("/v1/titles/{tid}/versions/{ver}/download/wad", response_model=bytes)
def download_wad(tid: str, ver: str):
    try:
        if ver == "latest":
            ver = None
        else:
            ver = int(ver)
            if ver < 0:
                ver = None
    except ValueError:
        ver = None

    title = libWiiPy.title.Title()
    # Get the TMD. If this fails, the Title likely does not exist, so return a 404.
    try:
        title.load_tmd(libWiiPy.title.download_tmd(tid, ver, wiiu_endpoint=True))
    except ValueError:
        raise TitleNotFoundException(tid=tid)
    # Get the Ticket. If this fails, the Title is probably not freely available, so return a 406.
    try:
        title.load_ticket(libWiiPy.title.download_ticket(tid, wiiu_endpoint=True))
    except ValueError:
        raise NoTicketException(tid=tid)
    # Get the content for this Title.
    title.load_content_records()
    title.content.content_list = libWiiPy.title.download_contents(tid, title.tmd, wiiu_endpoint=True)
    # Build the retail certificate chain.
    title.load_cert_chain(libWiiPy.title.download_cert_chain(wiiu_endpoint=True))
    # Generate required metadata and return the response.
    ver_final = ver if ver else title.tmd.title_version
    metadata = {
        "tid": tid,
        "version": ver_final,
    }
    headers = {
        'Content-Disposition': f'attachment; filename="{tid}-v{ver_final}.wad"',
        'X-Metadata': json.dumps(metadata),
        'Access-Control-Expose-Headers': 'X-Metadata',
    }
    response = Response(
        title.dump_wad(),
        headers=headers,
        media_type="application/octet-stream",
    )
    return response

@app.get("/v1/titles/{tid}/versions/{ver}/download/enc")
def download_enc(tid: str, ver: str):
    try:
        if ver == "latest":
            ver = None
        else:
            ver = int(ver)
            if ver < 0:
                ver = None
    except ValueError:
        ver = None

    # Get the TMD. If this fails, the Title likely does not exist, so return a 404.
    try:
        tmd = libWiiPy.title.TMD()
        tmd.load(libWiiPy.title.download_tmd(tid, ver, wiiu_endpoint=True))
    except ValueError:
        raise TitleNotFoundException(tid=tid)
    # Get the encrypted contents for the target version of the Title.
    content_list = libWiiPy.title.download_contents(tid, tmd, wiiu_endpoint=True)
    contents = []
    for i in range(len(tmd.content_records)):
        contents.append((f"{tmd.content_records[i].content_id:08X}", content_list[i]))
    # Create a zipfile in memory and add the TMD and encrypted contents to it.
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for content_name, content_data in contents:
            zip_file.writestr(content_name, content_data)
        zip_file.writestr("tmd", tmd.dump())
        for file in zip_file.filelist:
            file.create_system = 0
    # Generate required metadata and return the response.
    ver_final = ver if ver else tmd.title_version
    metadata = {
        "tid": tid,
        "version": ver_final,
    }
    headers = {
        'Content-Disposition': f'attachment; filename="{tid}-v{ver_final}-Encrypted.zip"',
        'X-Metadata': json.dumps(metadata),
        'Access-Control-Expose-Headers': 'X-Metadata',
    }
    response = Response(
        zip_buffer.getvalue(),
        headers=headers,
        media_type="application/zip"
    )
    return response

@app.get("/v1/titles/{tid}/versions/{ver}/download/dec")  # And the winner for "least efficient API endpoint" goes to...
def download_dec(tid: str, ver: str):
    try:
        if ver == "latest":
            ver = None
        else:
            ver = int(ver)
            if ver < 0:
                ver = None
    except ValueError:
        ver = None

    title = libWiiPy.title.Title()  # Use a Title because it's the fastest route to decryption.
    # Get the TMD. If this fails, the Title likely does not exist, so return a 404.
    try:
        title.load_tmd(libWiiPy.title.download_tmd(tid, ver, wiiu_endpoint=True))
    except ValueError:
        raise TitleNotFoundException(tid=tid)
    # Get the Ticket. If this fails, the Title is probably not freely available, so return a 406.
    try:
        title.load_ticket(libWiiPy.title.download_ticket(tid, wiiu_endpoint=True))
    except ValueError:
        raise NoTicketException(tid=tid)
    # Get the content for this Title.
    title.load_content_records()
    title.content.content_list = libWiiPy.title.download_contents(tid, title.tmd, wiiu_endpoint=True)
    # Get the encrypted contents for the target version of the Title. Using CID to ensure we match names correctly.
    contents = []
    for i in range(len(title.tmd.content_records)):
        contents.append((f"{title.tmd.content_records[i].content_id:08X}.app",
                         title.get_content_by_cid(title.tmd.content_records[i].content_id)))
    # Create a zipfile in memory and add the TMD, Ticket and decrypted contents to it.
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for content_name, content_data in contents:
            zip_file.writestr(content_name, content_data)
        zip_file.writestr("tmd", title.tmd.dump())
        zip_file.writestr("tik", title.ticket.dump())
        for file in zip_file.filelist:
            file.create_system = 0
    # Generate required metadata and return the response.
    ver_final = ver if ver else title.tmd.title_version
    metadata = {
        "tid": tid,
        "version": ver_final,
    }
    headers = {
        'Content-Disposition': f'attachment; filename="{tid}-v{ver_final}-Decrypted.zip"',
        'X-Metadata': json.dumps(metadata),
        'Access-Control-Expose-Headers': 'X-Metadata',
    }
    response = Response(
        zip_buffer.getvalue(),
        headers=headers,
        media_type="application/zip"
    )
    return response

@app.get("/v1/titles/{tid}/versions/{ver}/download/tad")
def download_tad(tid: str, ver: str):
    try:
        if ver == "latest":
            ver = None
        else:
            ver = int(ver)
            if ver < 0:
                ver = None
    except ValueError:
        ver = None

    title = libTWLPy.title.Title()
    # Get the TMD. If this fails, the Title likely does not exist, so return a 404.
    try:
        title.load_tmd(libTWLPy.download_tmd(tid, ver))
    except ValueError:
        raise TitleNotFoundException(tid=tid)
    # Get the Ticket. If this fails, the Title is probably not freely available, so return a 406.
    try:
        title.load_ticket(libTWLPy.download_ticket(tid))
    except ValueError:
        raise NoTicketException(tid=tid)
    # Get the content for this Title.
    title.load_content_records()
    title.content.content = libTWLPy.download_content(tid, title.tmd.content_record.content_id)
    # Build the retail certificate chain.
    title.tad.set_cert_data(libTWLPy.download_cert())
    # Generate required metadata and return the response.
    ver_final = ver if ver else title.tmd.title_version
    metadata = {
        "tid": tid,
        "version": ver_final,
    }
    headers = {
        'Content-Disposition': f'attachment; filename="{tid}-v{ver_final}.tad"',
        'X-Metadata': json.dumps(metadata),
        'Access-Control-Expose-Headers': 'X-Metadata',
    }
    response = Response(
        title.dump_tad(),
        headers=headers,
        media_type="application/octet-stream",
    )
    return response

@app.get('/version')
def get_version():
    result = {
        "libWiiPy Version": version("libWiiPy"),
        "libTWLPy Version": version("libTWLPy"),
    }
    return result

@app.get("/health")
def health_check():
    return {"status": "OK"}, 200

@app.get("/")
def hello_world():
  return "You've reached api.nusget.ninjacheetah.dev"
