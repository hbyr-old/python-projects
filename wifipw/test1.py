import cv2

# 打开视频文件
video = cv2.VideoCapture(0)

# 检查视频是否成功打开
if not video.isOpened():
    print("Error opening video file")

# 循环读取视频帧并显示
while video.isOpened():
    ret, frame = video.read()

    if ret:
        # 显示视频帧
        cv2.imshow('Video', frame)

        # 按下'q'键退出播放
        if cv2.waitKey(25) & 0xFF == ord('q'):
            break
    else:
        break

# 释放视频对象和关闭所有窗口
video.release()
cv2.destroyAllWindows()
