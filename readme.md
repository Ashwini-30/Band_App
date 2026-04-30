Got you bro — this is actually a **very strong, product-level project**, not just a script. I’ll give you a **clean, professional, GitHub-ready README** that reflects your vision (multi-page app + real-time FMG control + UI system).

---

# 📄 README.md

*(You can copy this directly into your repo)*

---

# ⚡ FMG Gesture-Based Smart Interaction System

A real-time **gesture-controlled interactive application** powered by an **FMG (Force Myography) band**, enabling seamless control over multiple domains including:

* 🎬 Media playback (YouTube-like player)
* 🎮 Gesture-based gaming (Subway Surfers style)
* 🛒 E-commerce browsing (gesture navigation)

This project combines **biomedical sensing + machine learning + human-computer interaction (HCI)** into a unified, production-style application.

---

## 🚀 Project Overview

This system uses **FMG + IMU signals** to classify hand gestures in real-time and map them to interactive controls across different applications.

The platform consists of **4 main UI pages**:

1. 🏠 Welcome Page
2. 🎬 Media Controller
3. 🎮 Gesture-Based Game
4. 🛒 E-commerce Interface

All interactions are performed **without keyboard/mouse**, purely via gestures.

---

## 🧠 Core Idea

Instead of traditional input devices, this system introduces:

> **"Touchless, muscle-driven interaction using wearable sensing"**

---

## 🎯 Features

### 🔹 Real-Time Gesture Classification

* Sliding window inference
* Feature extraction from:

  * FSR sensors (muscle pressure)
  * IMU (acceleration, gyroscope, orientation)
* ML Model: Extra Trees Classifier
* Latency-optimized pipeline

---

### 🔹 Gesture Set

| Gesture        | Action Mapping                     |
| -------------- | ---------------------------------- |
| 👍 Thumbs Up   | Play / Jump / Like                 |
| 👎 Thumbs Down | Pause / Slide Down / Unlike        |
| ✊ Fist Close   | Mute / Power / Add to Cart         |
| 🖐 Extend      | Volume Up / Move Right / Next      |
| 🤏 Flex        | Volume Down / Move Left / Previous |

---

## 🖥️ Application Modules

---

### 🏠 1. Welcome Page

* Clean UI introduction
* Gesture explanations with icons
* Navigation to all modules
* System status (Connected / Not connected)

---

### 🎬 2. Media Controller (YouTube-like)

Features:

* Video playback interface
* Gesture-based control:

  * Play/Pause
  * Volume control
  * Mute
* Side panel with recommended videos
* Real-time gesture display

---

### 🎮 3. Gesture-Based Game

Inspired by:

* Subway Surfers
* Temple Run

Controls:

* Flex → Move Left
* Extend → Move Right
* Thumbs Up → Jump
* Thumbs Down → Slide
* Fist Close → Power Boost

Features:

* Endless runner logic
* Obstacle avoidance
* Score tracking
* Smooth gesture responsiveness

---

### 🛒 4. E-commerce Interface

Features:

* Product carousel UI
* Gesture navigation:

  * Left/Right → Browse products
  * 👍 → Add to wishlist
  * 👎 → Remove
  * ✊ → Add to cart
* Clean modern UI (inspired by Amazon/Flipkart UX)

---

## 🏗️ System Architecture

```
FMG Band + IMU Sensors
        ↓
   Serial Data Stream
        ↓
 Sliding Window Buffer
        ↓
 Feature Extraction
        ↓
 ML Model (Extra Trees)
        ↓
 Gesture Prediction
        ↓
 UI Controller Engine
        ↓
 Multi-Page Application
```

---

## 📦 Tech Stack

### 🧠 Machine Learning

* scikit-learn (Extra Trees Classifier)
* numpy, pandas
* scipy (entropy features)

### 🔌 Hardware Interface

* PySerial

### 🎮 Interaction Layer

* pyautogui (keyboard emulation)

### 🖥️ UI Framework

* tkinter (current)
* *(future upgrade: PyQt / React / Electron)*

---

## ⚙️ Installation

```bash
git clone https://github.com/your-username/fmg-gesture-system.git
cd fmg-gesture-system

pip install -r requirements.txt
```

---

## ▶️ Running the Application

```bash
python main.py
```

Optional:

```bash
python main.py --port COM3
```

List available ports:

```bash
python main.py --list-ports
```

---

## 📊 Data Format

Incoming serial data:

```
roll,pitch,yaw,
ax,ay,az,
gx,gy,gz,
mx,my,mz,
fsr1,fsr2,fsr3,fsr4,fsr5,fsr6
```

---

## 🧪 Feature Engineering

* FSR:

  * Mean (rest vs gesture)
  * Peak
  * Activation ratio
* IMU:

  * Motion intensity
  * Orientation stability
* Statistical:

  * Mean, std, RMS, entropy
* Rest vs gesture segmentation

---

## 🧠 Model Details

* Algorithm: Extra Trees Classifier
* Input: Engineered feature vector
* Output: Gesture class + probability

---

## 📁 Project Structure

```
fmg-gesture-system/
│
├── main.py                  # Main application
├── model/
│   ├── extra_trees_model.pkl
│   └── scalers.pkl
│
├── ui/
│   ├── welcome_page.py
│   ├── media_page.py
│   ├── game_page.py
│   ├── ecommerce_page.py
│
├── utils/
│   ├── feature_extraction.py
│   ├── gesture_controller.py
│
├── assets/
│   ├── icons/
│   ├── videos/
│   ├── products/
│
└── README.md
```

---

## 🔥 Future Improvements

* 🔹 Deep Learning models (LSTM / CNN for temporal data)
* 🔹 Web-based UI (React + WebSockets)
* 🔹 AR/VR integration
* 🔹 Multi-user gesture recognition
* 🔹 Adaptive learning per user

---

## 💡 Applications

* Assistive technology
* Gaming interfaces
* Smart home control
* AR/VR interaction
* Touchless medical systems

---

## 📌 Inspiration

This project bridges:

* Biomedical Engineering
* Human-Computer Interaction
* Real-time Systems
* Intelligent Interfaces

---

## 👩‍💻 Author

**Ashwini Palani**
MTech Biomedical Engineering — IIT Madras

---

## 📎 Reference Code

Core implementation adapted and extended from your real-time controller:


---

## ⭐ Final Note

This is not just a project — this is a **full product prototype** showing:

> Real-time sensing → Intelligence → Interaction → Experience

---

If you want next step, I can help you:

* 🔥 Convert this into **full multi-page code (modular UI)**
* 🎨 Design **modern UI (Apple-level clean)**
* 🧠 Improve model (LSTM / Transformer)
* 📄 Prepare **paper for HCI journal**

Just tell me 👍
