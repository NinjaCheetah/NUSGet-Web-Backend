import io
from flask import Flask, jsonify, send_file
from flask_cors import CORS, cross_origin
from importlib.metadata import version
import libWiiPy
import json

api_ver = "1.0"

app = Flask(__name__)
cors = CORS(app, resources={r"/*": {"origins": ["https://nusget.ninjacheetah.dev", "http://localhost:4000", "http://127.0.0.1:4000"]}})
#app.config['CORS_HEADERS'] = 'Content-Type'

@app.get("/download/wad/")
def download_wad_no_args():
    error_response = {
        "Error": "No target Title ID or version was supplied."
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

    title = libWiiPy.title.download_title(tid, ver)
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

@app.route('/version', methods=['GET'])
def get_version():
    result = {
        "API Version": api_ver,
        "libWiiPy Version": version("libWiiPy")
    }
    return result

@app.route("/")
@cross_origin()
def hello_world():
  return "You're reached api.nusget.ninjacheetah.dev, which probably means you're in the wrong place."

if __name__ == '__main__':
    app.run()
