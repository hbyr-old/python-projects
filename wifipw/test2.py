import cv2
import mediapipe as mp
import webbrowser
import subprocess

# 初始化MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands()

# 初始化视频捕获
cap = cv2.VideoCapture(0)

# 定义OK手势的阈值
OK_THRESHOLD = 0.2

# 定义竖大拇指手势的阈值
THUMBS_UP_THRESHOLD = 0.2

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # 转换颜色空间到RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # 处理图像以检测手势
    results = hands.process(rgb_frame)

    # 检查是否检测到手
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # 获取手指尖的坐标
            thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
            index_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
            ring_tip = hand_landmarks.landmark[mp_hands.HandLandmark.RING_FINGER_TIP]
            pinky_tip = hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP]

            # 计算手指之间的距离
            thumb_index_distance = ((thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2)**0.5
            index_middle_distance = ((index_tip.x - middle_tip.x)**2 + (index_tip.y - middle_tip.y)**2)**0.5
            middle_ring_distance = ((middle_tip.x - ring_tip.x)**2 + (middle_tip.y - ring_tip.y)**2)**0.5
            ring_pinky_distance = ((ring_tip.x - pinky_tip.x)**2 + (ring_tip.y - pinky_tip.y)**2)**0.5

            # 检查是否是OK手势
            if thumb_index_distance < OK_THRESHOLD and index_middle_distance < OK_THRESHOLD and middle_ring_distance < OK_THRESHOLD and ring_pinky_distance < OK_THRESHOLD:
                # 关闭微信应用
                subprocess.call(['taskkill', '/F', '/IM', 'WeChat.exe'])  # 请根据你的微信安装路径修改

            # 检查是否是竖大拇指手势
            if thumb_tip.y < index_tip.y and thumb_tip.y < middle_tip.y and thumb_tip.y < ring_tip.y and thumb_tip.y < pinky_tip.y:
                # 打开微信应用
                subprocess.Popen(['D:\\Program Files\\Tencent\\WeChat\\WeChat.exe'])  # 请根据你的微信安装路径修改

    # 显示视频帧
    cv2.imshow('Hand Gesture Control', frame)

    # 按下'q'键退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 释放视频捕获和关闭所有窗口
cap.release()
cv2.destroyAllWindows()
