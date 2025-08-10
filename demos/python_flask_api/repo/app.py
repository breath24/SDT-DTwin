from flask import Flask, request, jsonify

app = Flask(__name__)

@app.get('/')
def home():
    return jsonify({"ok": True})

# TODO: implement /add?a=1&b=2 -> {"result": 3}
# Return 400 with {"error": "bad_request"} on invalid inputs

if __name__ == '__main__':
    app.run(debug=True)
