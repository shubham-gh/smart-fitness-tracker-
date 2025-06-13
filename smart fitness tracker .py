import streamlit as st
import mediapipe as mp
import cv2
import numpy as np
import pyttsx3
import time
import requests
from twilio.rest import Client

# --------- API KEYS & CONFIG (Fill your keys here) ---------
TWILIO_ACCOUNT_SID = 'your_twilio_sid'
TWILIO_AUTH_TOKEN = 'your_twilio_auth_token'
TWILIO_PHONE_NUMBER = 'your_twilio_phone'
NUTRITIONIX_APP_ID = 'your_nutritionix_app_id'
NUTRITIONIX_API_KEY = 'your_nutritionix_api_key'
NUTRITIONIX_API_URL = 'https://trackapi.nutritionix.com/v2/natural/exercise'
SHEETY_API_URL = 'your_sheety_api_url'

# --------- Utility Functions ---------
def send_sms(exercise_name, reps, calories_burned, user_phone_number):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = f"Exercise: {exercise_name}\nReps: {reps}\nCalories: {calories_burned:.2f} kcal"
        client.messages.create(body=message, from_=TWILIO_PHONE_NUMBER, to=user_phone_number)
        st.success("✅ SMS sent successfully!")
    except Exception as e:
        st.error(f"❌ SMS Failed: {e}")

def get_calories_burned(exercise, weight, reps, height, age, gender):
    headers = {
        'x-app-id': NUTRITIONIX_APP_ID,
        'x-app-key': NUTRITIONIX_API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        "query": f"{reps} reps of {exercise}",
        "gender": gender,
        "weight_kg": weight,
        "height_cm": height,
        "age": age
    }
    response = requests.post(NUTRITIONIX_API_URL, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        return result['exercises'][0]['nf_calories'] / reps
    return 0

def log_to_sheet(exercise, weight, reps, height, age, gender, calories):
    headers = {'Content-Type': 'application/json'}
    data = {
        "sheet1": {
            "exercise": exercise,
            "weight": weight,
            "reps": reps,
            "height": height,
            "age": age,
            "gender": gender,
            "calories": calories
        }
    }
    response = requests.post(SHEETY_API_URL, headers=headers, json=data)
    if response.status_code != 201:
        st.error("❌ Failed to log data to Google Sheets")

# --------- Exercise Counter Helper ---------
mp_pose = mp.solutions.pose

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radians = np.arccos(np.clip(np.dot(b - a, c - b) / (np.linalg.norm(b - a) * np.linalg.norm(c - b)), -1.0, 1.0))
    return np.degrees(radians)

# --------- Background styling function ---------
def set_background():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("https://images.pexels.com/photos/1229356/pexels-photo-1229356.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# --------- Main App ---------
def main():
    st.set_page_config(layout="wide")
    set_background()
    st.title("🏋️ Fitness Tracker")

    with st.sidebar:
        st.header("📋 User Info")
        exercise = st.selectbox("Select Exercise", ["bicep curls", "lateral raises"])
        weight = st.slider("Weight (kg)", 40, 120, 70)
        height = st.slider("Height (cm)", 140, 200, 170)
        age = st.slider("Age", 15, 70, 25)
        gender = st.radio("Gender", ["male", "female"])
        phone = st.text_input("Phone Number", max_chars=13)
        st.header("🎮 Controls")
        start_btn = st.button("▶ Start Exercise")
        stop_btn = st.button("⏹ Stop Exercise")

    if "run" not in st.session_state:
        st.session_state.run = False
    if "count" not in st.session_state:
        st.session_state.count = 0
    if "calories" not in st.session_state:
        st.session_state.calories = 0
    if "stage" not in st.session_state:
        st.session_state.stage = None
    if "cal_per_rep" not in st.session_state:
        st.session_state.cal_per_rep = 0
    if "engine" not in st.session_state:
        st.session_state.engine = pyttsx3.init()

    if start_btn:
        st.session_state.run = True
        st.session_state.count = 0
        st.session_state.calories = 0
        st.session_state.stage = None
        st.session_state.cal_per_rep = 0

    if stop_btn:
        st.session_state.run = False
        if st.session_state.count > 0:
            send_sms(exercise, st.session_state.count, st.session_state.calories, phone)
            log_to_sheet(exercise, weight, st.session_state.count, height, age, gender, st.session_state.calories)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("Live Webcam")
        webcam_placeholder = st.empty()

    with col2:
        st.header("Demo Video")
        if exercise == "bicep curls":
            st.video("https://www.youtube.com/embed/sAq_ocpRh_I")
        elif exercise == "lateral raises":
            st.video("https://www.youtube.com/watch?v=3VcKaXpzqRo")

    if st.session_state.run:
        cap = cv2.VideoCapture(0)
        rep_text = st.empty()

        with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            while st.session_state.run:
                ret, frame = cap.read()
                if not ret:
                    st.error("Failed to open webcam")
                    break

                frame = cv2.flip(frame, 1)
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(img_rgb)

                if results.pose_landmarks:
                    landmarks = results.pose_landmarks.landmark
                    ls = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                          landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
                    le = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                          landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
                    lw = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                          landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
                    angle = calculate_angle(ls, le, lw)

                    if angle > 160:
                        st.session_state.stage = "down"
                    if angle < 30 and st.session_state.stage == "down":
                        st.session_state.stage = "up"
                        st.session_state.count += 1
                        if st.session_state.count == 1:
                            st.session_state.cal_per_rep = get_calories_burned(
                                exercise, weight, 1, height, age, gender)
                        st.session_state.calories += st.session_state.cal_per_rep
                        st.session_state.engine.say(str(st.session_state.count))
                        st.session_state.engine.runAndWait()

                    mp.solutions.drawing_utils.draw_landmarks(
                        frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

                rep_text.markdown(
                    f"### Reps: {st.session_state.count}  \nCalories Burned: {st.session_state.calories:.2f} kcal")
                webcam_placeholder.image(frame, channels="BGR")
                time.sleep(0.03)

        cap.release()
        cv2.destroyAllWindows()
    else:
        st.info("Click ▶ Start Exercise from the sidebar to begin.")

if __name__ == "__main__":
    main()
