import io
from flask import Flask, jsonify, send_file
from flask_cors import CORS, cross_origin
from importlib.metadata import version
import libWiiPy
import libTWLPy
import json

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

    metadata = {
        "tid": tid,
        "version": ver if ver else title.tmd.title_version,
    }

    response = send_file(
        file_data,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=f"{tid}-v{ver}.wad"
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

    metadata = {
        "tid": tid,
        "version": ver if ver else title.tmd.title_version,
    }

    response = send_file(
        file_data,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=f"{tid}-v{ver}.tad"
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
