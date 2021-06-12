from flask import Flask,jsonify,request,render_template
from werkzeug.utils import secure_filename
import mysql.connector
import os
import face_recognition as fr
import datetime
import json
import numpy as np
import time
from flask_swagger_ui import get_swaggerui_blueprint
from dotenv import load_dotenv
from flask_cors import CORS,cross_origin
from pytz import timezone

timezone = timezone('Asia/Kolkata')

load_dotenv()

mydb = mysql.connector.connect(
  host=os.getenv("DB_HOST"),
  user=os.getenv("DB_USER"),
  password=os.getenv("DB_PASSWORD"),
  database=os.getenv("DB_NAME")
)

mycursor = mydb.cursor()

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)

SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
SWAGGERUI_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Face Recognition"
    }
)
app.register_blueprint(SWAGGERUI_BLUEPRINT, url_prefix=SWAGGER_URL)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

CORS(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convertToBinaryData(filename):
    # Convert digital data to binary format
    with open(filename, 'rb') as file:
        binaryData = file.read()
    return binaryData

# Endpoint for registration
@app.route('/')
@cross_origin()
def home():
    return render_template('index.html')

# Endpoint for registration
@app.route('/register',methods=["POST"])
@cross_origin()
def register():
    start_time = time.time()
    if request.method == 'POST':
        # checking if name already exists
        name = request.form['name']
        if name.isspace() or name=='':
            del name
            return jsonify({"status":416,"message":"No name is entered"})
        mycursor.execute("SELECT student_name FROM students_table")
        results = mycursor.fetchall()
        for i in results:
           if name in i:
               del results
               return jsonify({"status":400,"message":"Name is already taken"})
        institute = request.form['institute']

        gender = request.form['gender']
        if gender.isspace() or gender=='':
            del gender
            return jsonify({"status":416,"message":"No gender is entered"})        

        # check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({"status":406,"message":"File variable not included in request"})
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            del file,name,results
            return jsonify({"status":406,"message":"No image uploaded"})
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)
            ct = datetime.datetime.now(timezone)
            try:
                img = fr.load_image_file(path)
                embedding = fr.face_encodings(img)[0]
            except:
                os.remove(path)
                del filename,file,path,img,ct,results,name
                return jsonify({"status":401,"message":"Unable to detect face"})

            x = convertToBinaryData(path)
            try:
                mycursor.execute("INSERT INTO students_table(institute_id, student_name, student_gender, student_embedding, created_at) VALUES (%s,%s,%s,%s,%s)",(institute,name,gender,json.dumps(list(embedding)),ct))
                mydb.commit()
            except:
                return jsonify({"status":501,"message":"Error while inserting data into students_table"})
            try:
                mycursor.execute("SELECT student_id FROM students_table WHERE student_name=%s AND institute_id=%s",(name,institute))
                results = mycursor.fetchall()
            except:
                return jsonify({"status":501,"message":"Error while fetching student id from students_table"})
            try:
                mycursor.execute("INSERT INTO students_image(student_id, institute_id, student_gender, student_image, created_at) VALUES (%s,%s,%s,%s,%s)",(results[0][0],institute,gender,x,ct))
                mydb.commit()
            except:
                return jsonify({"status":501,"message":"Error while inserting data into students_image"})
            os.remove(path)
            end_time = time.time()
            del filename,file,path,img,x,ct,results
            return jsonify({"status":200,"message":"User details registered","time_taken":end_time-start_time})
    return jsonify({"status":404,"message":"Not a valid route"})
    


# Endpoint for verification
@app.route('/verify',methods=["POST"])
@cross_origin()
def verify():
    start_time = time.time()
    if request.method == 'POST':
        institute = request.form['institute']

        gender = request.form['gender']
        if gender.isspace() or gender=='':
            del gender
            return jsonify({"status":416,"message":"No gender is entered"})
        # check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({"status":406,"message":"File variable not included in request"})
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            return jsonify({"status":406,"message":"No image uploaded"})
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            file.save(path)
            ct = datetime.datetime.now()

            try:
                img = fr.load_image_file(path)
                embedding = fr.face_encodings(img)[0]
            except:
                os.remove(path)
                return jsonify({"status":401,"message":"Unable to detect face"})

            x = convertToBinaryData(path)
            try:
                mycursor.execute("SELECT student_name,student_embedding FROM students_table WHERE student_gender=%s AND institute_id=%s",(gender,institute))
                results = mycursor.fetchall()
            except:
                return jsonify({"status":502,"message":"Error while fetching data from students_table"})
            embeddings = []
            names = []

            for i in results:
                names.append(i[0])
                embeddings.append(list(json.loads(i[1])))
            results = fr.compare_faces(embeddings, embedding)
            if True not in results:
                os.remove(path)
                return jsonify({"status":204,"message":"User doesn't exist in database"})
            detectedFace = names[np.argmax(results)]

            os.remove(path)
            end_time = time.time()
            del names
            del embeddings
            del ct 
            del results
            del filename,file,path,img,x
            try:
                mycursor.execute("SELECT student_id FROM students_table WHERE student_name=%s AND institute_id=%s",(detectedFace,institute))
                results = mycursor.fetchall()
            except:
                return jsonify({"status":502,"message":"Error while fetching student id from students_table"})
            return jsonify({"status":200,"message":"User verified","name":detectedFace,"student_id":results[0][0],"time_taken":end_time-start_time})
    return jsonify({"status":404,"message":"Not a valid route"})


if __name__ == '__main__':
    app.secret_key = os.getenv("SECRET_KEY")
    app.run(debug = False ,host=os.getenv("APP_HOST"),port=os.getenv("APP_PORT"))