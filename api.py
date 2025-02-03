# "api.py" from NUSGet-Web-Backend by NinjaCheetah
# https://github.com/NinjaCheetah/NUSGet-Web-Backend

from importlib.metadata import version
import io
import json
import zipfile

from flask import Flask, jsonify, send_file, request
from flask_cors import CORS, cross_origin
import libWiiPy
import libTWLPy


api_ver = "1.0"

app = Flask(__name__)
cors = CORS(app, resources={r"/*": {"origins": ["https://nusget.ninjacheetah.dev", "http://localhost:4000", "http://127.0.0.1:4000"]}})

@app.get("/download/wad/")
def download_wad_no_args():
    error_response = {
        "Error": "No target Title ID or version was supplied.",
        "Cat": "https://http.cat/images/400.jpg"
    }
    return error_response, 400

@app.get("/download/wad/<string:tid>/<string:ver>")
def download_wad(tid, ver):
    try:
        ver = int(ver)
        if ver == -1:
            ver = None
    except ValueError:
        ver = None

    title = libWiiPy.title.Title()
    # Get the TMD. If this fails, the Title likely does not exist, so return a 404.
    try:
        title.load_tmd(libWiiPy.title.download_tmd(tid, ver, wiiu_endpoint=True))
    except ValueError:
        response = {
            "Error": "The requested Title or version could not be found.",
            "Cat": "https://http.cat/images/404.jpg"
        }
        return response, 404
    # Get the Ticket. If this fails, the Title is probably not freely available, so return a 403.
    try:
        title.load_ticket(libWiiPy.title.download_ticket(tid, wiiu_endpoint=True))
    except ValueError:
        response = {
            "Error": "No Ticket is available for the requested Title.",
            "Cat": "https://http.cat/images/403.jpg"
        }
        return response, 403
    # Get the content for this Title.
    title.load_content_records()
    title.content.content_list = libWiiPy.title.download_contents(tid, title.tmd, wiiu_endpoint=True)
    # Build the retail certificate chain.
    title.load_cert_chain(libWiiPy.title.download_cert_chain(wiiu_endpoint=True))
    # Dump the WAD so we can hand it over.
    file_data = io.BytesIO(title.dump_wad())

    ver_final = ver if ver else title.tmd.title_version
    metadata = {
        "tid": tid,
        "version": ver_final,
    }
    response = send_file(
        file_data,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=f"{tid}-v{ver_final}.wad"
    )

    response.headers["X-Metadata"] = json.dumps(metadata)
    response.headers["Access-Control-Expose-Headers"] = "X-Metadata"

    return response

@app.get("/download/enc/<string:tid>/<string:ver>")
def download_enc(tid, ver):
    try:
        ver = int(ver)
        if ver == -1:
            ver = None
    except ValueError:
        ver = None

    # Get the TMD. If this fails, the Title likely does not exist, so return a 404.
    try:
        tmd = libWiiPy.title.TMD()
        tmd.load(libWiiPy.title.download_tmd(tid, ver, wiiu_endpoint=True))
    except ValueError:
        response = {
            "Error": "The requested Title or version could not be found.",
            "Cat": "https://http.cat/images/404.jpg"
        }
        return response, 404
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
    out_buffer = io.BytesIO(zip_buffer.getvalue())

    ver_final = ver if ver else tmd.title_version
    metadata = {
        "tid": tid,
        "version": ver_final,
    }
    response = send_file(
        out_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{tid}-v{ver_final}-Encrypted.zip"
    )

    response.headers["X-Metadata"] = json.dumps(metadata)
    response.headers["Access-Control-Expose-Headers"] = "X-Metadata"

    return response

@app.get("/download/dec/<string:tid>/<string:ver>")  # And the winner for "least efficient API endpoint" goes to...
def download_dec(tid, ver):
    try:
        ver = int(ver)
        if ver == -1:
            ver = None
    except ValueError:
        ver = None

    title = libWiiPy.title.Title()  # Use a Title because it's the fastest route to decryption.
    # Get the TMD. If this fails, the Title likely does not exist, so return a 404.
    try:
        title.load_tmd(libWiiPy.title.download_tmd(tid, ver, wiiu_endpoint=True))
    except ValueError:
        response = {
            "Error": "The requested Title or version could not be found.",
            "Cat": "https://http.cat/images/404.jpg"
        }
        return response, 404
    # Get the Ticket. If this fails, the Title is probably not freely available, so return a 403.
    try:
        title.load_ticket(libWiiPy.title.download_ticket(tid, wiiu_endpoint=True))
    except ValueError:
        response = {
            "Error": "No Ticket is available for the requested Title.",
            "Cat": "https://http.cat/images/403.jpg"
        }
        return response, 403
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
    out_buffer = io.BytesIO(zip_buffer.getvalue())

    ver_final = ver if ver else title.tmd.title_version
    metadata = {
        "tid": tid,
        "version": ver_final,
    }
    response = send_file(
        out_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{tid}-v{ver_final}-Decrypted.zip"
    )

    response.headers["X-Metadata"] = json.dumps(metadata)
    response.headers["Access-Control-Expose-Headers"] = "X-Metadata"

    return response

@app.get("/download/tad/<string:tid>/<string:ver>")
def download_tad(tid, ver):
    try:
        ver = int(ver)
        if ver == -1:
            ver = None
    except ValueError:
        ver = None

    title = libTWLPy.title.Title()
    # Get the TMD. If this fails, the Title likely does not exist, so return a 404.
    try:
        title.load_tmd(libTWLPy.download_tmd(tid, ver))
    except ValueError:
        response = {
            "Error": "The requested Title or version could not be found.",
            "Cat": "https://http.cat/images/404.jpg"
        }
        return response, 404
    # Get the Ticket. If this fails, the Title is probably not freely available, so return a 403.
    try:
        title.load_ticket(libTWLPy.download_ticket(tid))
    except ValueError:
        response = {
            "Error": "No Ticket is available for the requested Title.",
            "Cat": "https://http.cat/images/403.jpg"
        }
        return response, 403
    # Get the content for this Title.
    title.load_content_records()
    title.content.content = libTWLPy.download_content(tid, title.tmd.content_record.content_id)
    # Build the retail certificate chain.
    title.tad.set_cert_data(libTWLPy.download_cert())
    # Dump the WAD so we can hand it over.
    file_data = io.BytesIO(title.dump_tad())

    ver_final = ver if ver else title.tmd.title_version
    metadata = {
        "tid": tid,
        "version": ver_final,
    }
    response = send_file(
        file_data,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=f"{tid}-v{ver_final}.tad"
    )

    response.headers["X-Metadata"] = json.dumps(metadata)
    response.headers["Access-Control-Expose-Headers"] = "X-Metadata"

    return response

@app.route('/version', methods=['GET'])
def get_version():
    result = {
        "API Version": api_ver,
        "libWiiPy Version": version("libWiiPy"),
        "libTWLPy Version": version("libTWLPy"),
    }
    return result

@app.route("/")
@cross_origin()
def hello_world():
  return "You're reached api.nusget.ninjacheetah.dev, which probably means you're in the wrong place."

if __name__ == '__main__':
    app.run()
