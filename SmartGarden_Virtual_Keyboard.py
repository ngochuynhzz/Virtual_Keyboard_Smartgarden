import cv2
import Jetson.GPIO as GPIO
import serial
from cvzone.HandTrackingModule import HandDetector
from time import sleep, time
import numpy as np
import cvzone
from pynput.keyboard import Controller, Key
import os
import traceback # Để in chi tiết lỗi

# CÀI ĐẶT BAN ĐẦU
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("LỖI: Không thể mở webcam! Vui lòng kiểm tra lại camera.")
    exit()

cap.set(3, 1280)
cap.set(4, 720)

try:
    keyboard = Controller()
except Exception as e_controller:
    print(f"LỖI: Không thể khởi tạo pynput Controller: {e_controller}")
    print("Vui lòng kiểm tra cấu hình hệ thống của bạn cho pynput (ví dụ: DISPLAY server trên Linux).")
    keyboard = None
else:
    print("INFO: Pynput Controller khởi tạo thành công.")


detector = HandDetector(detectionCon=0.8, maxHands=1)
keys = [["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
        ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
        ["A", "S", "D", "F", "G", "H", "J", "K", "L", ";"],
        ["Z", "X", "C", "V", "B", "N", "M", ",", ".", " ", "<"]]
finalText = ""

# BIẾN TOÀN CỤC VÀ HẰNG SỐ CHO CÁC TRẠNG THÁI
program_state = "NORMAL"
password_input = ""
password_attempts = 0
CORRECT_PASSWORD = "nhom8"
MAX_ATTEMPTS = 3

# CÀI ĐẶT JETSON GPIO VÀ  GIAO TIẾP UART
JETSON_MODE = True
led_pins_board = [11, 13, 15]
led_status = False 
ser = None

if JETSON_MODE:
    try:
        GPIO.setmode(GPIO.BOARD)
        for pin in led_pins_board:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        
        # Mở cổng UART, khớp với 9600 baud của Arduino
        ser = serial.Serial("/dev/ttyTHS1", 9600, timeout=0.5) 
        print("INFO: Jetson GPIO and UART initialized successfully.")
    except ImportError:
        print("LỖI: Không tìm thấy thư viện Jetson.GPIO hoặc pyserial. Chuyển sang chế độ không Jetson.")
        JETSON_MODE = False
    except Exception as e:
        print(f"LỖI: Không thể khởi tạo Jetson GPIO/UART. Chuyển sang chế độ không Jetson. Chi tiết: {e}")
        JETSON_MODE = False
else:
    print("INFO: Chạy ở chế độ không Jetson (JETSON_MODE=False ban đầu).")

# TẢI GIAO DIỆN
background_image = None
try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
    image_path = os.path.join(script_dir, "GIAODIEN.jpg")
    if os.path.exists(image_path):
        background_image = cv2.imread(image_path)
        if background_image is not None:
            background_image = cv2.resize(background_image, (1280, 720))
            print("INFO: Tải và resize GIAODIEN.jpg thành công.")
        else:
             print("THÔNG BÁO: GIAODIEN.jpg bị lỗi. Dùng nền đen.")
    else:
        print("THÔNG BÁO: File GIAODIEN.jpg không tồn tại. Dùng nền đen.")
except Exception as e:
    print(f"LỖI khi tải GIAODIEN.jpg: {e}")
    background_image = None

# DANH SÁCH NÚT GIAO DIỆN VƯỜN
garden_buttons = [
    {'name': 'Mo May Bom', 'rect': (500, 115, 270, 75)},
    {'name': 'Mo Den', 'rect': (530, 260, 210, 75)},
    {'name': 'Doc Cam Bien', 'rect': (460, 400, 360, 85)},
    {'name': 'Thoat', 'rect': (960, 620, 290, 70)}
]
garden_action_text = ""

# LỚP VÀ DANH SÁCH NÚT BÀN PHÍM
class Button():
    def __init__(self, pos, text, size=[85, 85]):
        self.pos = pos
        self.size = size
        self.text = text

buttonList = []
for i in range(len(keys)):
    for j, key_char in enumerate(keys[i]):
        buttonList.append(Button([100 * j + 50, 100 * i + 50], key_char))

# CÁC HÀM VẼ
# (Giữ nguyên các hàm draw_keyboard_button và draw_garden_button)
DEFAULT_COLOR = (255, 0, 255); HOVER_COLOR = (175, 0, 175); PRESS_COLOR = (0, 255, 0)
TEXT_COLOR = (255, 255, 255); PRESS_TEXT_COLOR = (0, 0, 0)
def draw_keyboard_button(img_draw, button, state="default"):
    x, y, w, h = button.pos[0], button.pos[1], button.size[0], button.size[1]
    current_fill_color, current_text_color = DEFAULT_COLOR, TEXT_COLOR
    if state == "hover": current_fill_color = HOVER_COLOR
    elif state == "press": current_fill_color, current_text_color = PRESS_COLOR, PRESS_TEXT_COLOR
    cv2.rectangle(img_draw, (x, y), (x + w, y + h), current_fill_color, cv2.FILLED)
    cvzone.cornerRect(img_draw, (x, y, w, h), 20, rt=2, colorC=(200, 200, 200))
    cv2.putText(img_draw, button.text, (x + 20, y + 65), cv2.FONT_HERSHEY_PLAIN, 4, current_text_color, 4)

def draw_garden_button(img_draw, button, state="default"):
    x, y, w, h = button['rect']
    color_fill_default = (255, 255, 255); color_border_default = (0, 0, 255); color_text_default = (0, 0, 0)
    thickness_border = 3
    current_fill_color, current_border_color, current_text_color = color_fill_default, color_border_default, color_text_default
    if state == "hover": current_fill_color, current_border_color = (230, 230, 230), (0, 0, 200)
    elif state == "press": current_fill_color, current_border_color = (200, 255, 200), (0, 200, 0)
    cv2.rectangle(img_draw, (x, y), (x + w, y + h), current_fill_color, cv2.FILLED)
    cv2.rectangle(img_draw, (x, y), (x + w, y + h), current_border_color, thickness_border)
    button_name_to_draw = button['name']
    font_scale, font_thickness = 1.2, 2
    (text_width, text_height), _ = cv2.getTextSize(button_name_to_draw, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
    text_x, text_y = x + (w - text_width) // 2, y + (h + text_height) // 2
    cv2.putText(img_draw, button_name_to_draw, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, current_text_color, font_thickness)

# HÀM ĐIỀU KHIỂN PHẦN CỨNG CHO BẬT/TẮT LEDS
def set_leds_state(turn_on):
    global led_status
    if JETSON_MODE and 'GPIO' in globals():
        try:
            output_state = GPIO.HIGH if turn_on else GPIO.LOW
            for pin in led_pins_board:
                GPIO.output(pin, output_state)
            led_status = turn_on
            print(f"INFO: LEDs turned {'ON' if turn_on else 'OFF'}.")
        except Exception as e_gpio:
            print(f"LỖI khi điều khiển GPIO: {e_gpio}")
    else:
        led_status = turn_on
        print(f"SIMULATE: LEDs turned {'ON' if turn_on else 'OFF'}.")

# Hàm đọc cảm biến được cập nhật để gửi lệnh 'C'
def read_uart_data_from_sensor():
    if JETSON_MODE and ser and ser.is_open:
        try:
            ser.write(b'C')  # Gửi lệnh 'C' để yêu cầu dữ liệu
            ser.flush()      # Đảm bảo lệnh được gửi đi
            sleep(0.1)       # Đợi Arduino phản hồi
            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8").strip()
                return line if line else "Khong co du lieu moi"
            else:
                return "Khong co phan hoi tu Arduino"
        except Exception as e:
            print(f"LỖI khi giao tiếp UART: {e}")
            return "Loi doc/ghi UART"
    elif not JETSON_MODE:
        sim_temp = 25 + (time() % 10) / 2
        sim_humid = 60 + (time() % 20) / 2
        return f"Mo phong: Nhiet: {sim_temp:.1f}C, Do Am: {sim_humid:.1f}%"
    return "Loi UART (chua khoi tao)"

# Hàm mới để gửi lệnh "B" bật/tắt máy bơm thông qua giao tiếp UART
def toggle_pump_via_uart():
    global garden_action_text
    if JETSON_MODE and ser and ser.is_open:
        try:
            ser.write(b'B') # Gửi lệnh 'B' để bật/tắt bơm
            ser.flush()
            sleep(0.1) # Đợi phản hồi xác nhận từ Arduino
            if ser.in_waiting > 0:
                response = ser.readline().decode("utf-8").strip()
                garden_action_text = response # Hiển thị xác nhận từ Arduino
            else:
                garden_action_text = "Lenh 'B' da gui, khong co phan hoi"
        except Exception as e:
            garden_action_text = f"LOI GUI LENH 'B': {e}"
    else:
        garden_action_text = "SIMULATE: Gui lenh bat/tat bom"
        print(garden_action_text)

# CÀI ĐẶT NHẤN VÀ THẢ
CLICK_DISTANCE, ACTION_COOLDOWN = 35, 0.5 # Tăng cooldown một chút
last_action_time, is_clicking, button_being_pressed = 0, False, None

# CỬA SỔ FULLSCREEN 
cv2.namedWindow("Image", cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty("Image", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# VÒNG LẶP CHÍNH
try:
    while True:
        try:
            success, img_raw = cap.read() 
            if not success: 
                print("LỖI: Không thể đọc frame từ webcam. Đang thử lại...")
                sleep(0.5)
                continue
            
            img_flipped = cv2.flip(img_raw, 1) 
            hands, img_processed_hands = detector.findHands(img_flipped, draw=True, flipType=False)

            lmList_interaction = []
            physical_hand_type_for_logic = "Unknown" 
            hand_info_for_display = "No hand detected"
            button_hovered = None

            if hands:
                current_hand = hands[0]
                actual_lmList = current_hand['lmList']
                physical_hand_type_for_logic = current_hand['type']
                hand_info_for_display = f"Hand: {physical_hand_type_for_logic}"

                if physical_hand_type_for_logic == "Right":
                    lmList_interaction = actual_lmList 
                    hand_info_for_display += " (Active)"
                    
                    if len(lmList_interaction) >= 13:
                        # Kiểm tra hover
                        if program_state == "GARDEN_CONTROL":
                            for button_spec in garden_buttons:
                                x, y, w, h = button_spec['rect']
                                if x < lmList_interaction[8][0] < x + w and y < lmList_interaction[8][1] < y + h:
                                    button_hovered = button_spec['name']
                                    break
                        else: # Bàn phím
                            for button_obj in buttonList:
                                x, y, w, h = button_obj.pos[0], button_obj.pos[1], button_obj.size[0], button_obj.size[1]
                                if x < lmList_interaction[8][0] < x + w and y < lmList_interaction[8][1] < y + h:
                                    button_hovered = button_obj.text
                                    break
                        
                        # Kiểm tra click
                        distance, _ = detector.findDistance(lmList_interaction[8][0:2], lmList_interaction[12][0:2])

                        if distance < CLICK_DISTANCE:
                            if not is_clicking and button_hovered:
                                is_clicking = True
                                button_being_pressed = button_hovered
                        else:
                            if is_clicking and button_being_pressed is not None:
                                if time() - last_action_time > ACTION_COOLDOWN:
                                    
                                    # --- XỬ LÝ HÀNH ĐỘNG ---
                                    if program_state == "NORMAL":
                                        # ... (giữ nguyên logic bàn phím)
                                        if keyboard:
                                            if button_being_pressed == '<':
                                                if finalText: finalText = finalText[:-1]
                                                keyboard.press(Key.backspace); keyboard.release(Key.backspace); sleep(0.15)
                                            elif button_being_pressed:
                                                finalText += button_being_pressed
                                                try:
                                                    if isinstance(button_being_pressed, str) and len(button_being_pressed) == 1:
                                                        keyboard.press(button_being_pressed)
                                                        keyboard.release(button_being_pressed)
                                                except Exception as e_keypress:
                                                    print(f"Lỗi khi mô phỏng nhấn phím '{button_being_pressed}': {e_keypress}")
                                                sleep(0.15)
                                        if finalText == "11;":
                                            program_state = "PASSWORD_ENTRY"
                                            finalText = ""
                                            password_input = ""
                                            password_attempts = 0
                                            garden_action_text = ""
                                    
                                    elif program_state == "PASSWORD_ENTRY":
                                        # ... (giữ nguyên logic mật khẩu)
                                        if button_being_pressed == '<':
                                            if password_input: password_input = password_input[:-1]
                                        elif button_being_pressed == ';':
                                            if password_input.lower() == CORRECT_PASSWORD:
                                                program_state = "GARDEN_CONTROL"
                                                garden_action_text = "DANG NHAP THANH CONG!"
                                            else:
                                                password_attempts += 1
                                                password_input = ""
                                                if password_attempts >= MAX_ATTEMPTS:
                                                    garden_action_text = "HET LUOT THU. QUAY LAI."
                                                    program_state = "NORMAL"
                                                    password_attempts = 0 
                                                else:
                                                    garden_action_text = f"SAI MAT KHAU. CON {MAX_ATTEMPTS - password_attempts} LAN."
                                        elif button_being_pressed and button_being_pressed != " ":
                                            password_input += button_being_pressed
                                    
                                    elif program_state == "GARDEN_CONTROL":
                                        if button_being_pressed == 'Mo Den':
                                            set_leds_state(not led_status)
                                            garden_action_text = f"DEN LED DA {'BAT' if led_status else 'TAT'}"
                                        
                                        # Gọi hàm để điều khiển máy bơm
                                        elif button_being_pressed == 'Mo May Bom':
                                            toggle_pump_via_uart()
                                        
                                        elif button_being_pressed == 'Doc Cam Bien':
                                            sensor_data = read_uart_data_from_sensor()
                                            garden_action_text = f"CAM BIEN: {sensor_data}"
                                        
                                        elif button_being_pressed == 'Thoat':
                                            program_state = "NORMAL"
                                            finalText, garden_action_text, password_input = "", "", ""
                                            password_attempts = 0 
                                            if JETSON_MODE and led_status:
                                                set_leds_state(False)
                                    
                                    last_action_time = time()
                                is_clicking = False
                                button_being_pressed = None

            # LOGIC VẼ GIAO DIỆN
            final_display_image = img_processed_hands.copy()

            if program_state == "GARDEN_CONTROL":
                if background_image is None: 
                    final_display_image = np.zeros((720, 1280, 3), np.uint8)
                    cv2.putText(final_display_image, "LOI: KHONG TIM THAY GIAODIEN.jpg", (50, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255),3)
                else:
                    final_display_image = background_image.copy()
                
                for button_item in garden_buttons:
                    state = "default"
                    if button_being_pressed == button_item['name'] and is_clicking : state = "press"
                    elif button_hovered == button_item['name']: state = "hover"
                    draw_garden_button(final_display_image, button_item, state)
                
                cv2.rectangle(final_display_image, (10, 650), (940, 710), (0,0,0), cv2.FILLED)
                cv2.putText(final_display_image, garden_action_text, (30, 695), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 255, 255), 2)
                
                if lmList_interaction:
                    # Vẽ con trỏ là đầu ngón trỏ
                    cv2.circle(final_display_image, (lmList_interaction[8][0], lmList_interaction[8][1]), 10, (0, 255, 0), cv2.FILLED)
                
                cv2.putText(final_display_image, hand_info_for_display, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)
            
            else: # Vẽ màn hình NORMAL hoặc PASSWORD_ENTRY
                # (Giữ nguyên logic vẽ bàn phím và ô nhập liệu)
                overlay_rect = final_display_image.copy()
                cv2.rectangle(overlay_rect, (int(0.02*1280), int(0.05*720)), (int(0.98*1280), int(0.9*720)), (128,0,128), -1)
                alpha = 0.6
                final_display_image = cv2.addWeighted(overlay_rect, alpha, final_display_image, 1 - alpha, 0)
                
                for btn_to_draw in buttonList:
                    state = "default"
                    if button_being_pressed == btn_to_draw.text and is_clicking: state = "press"
                    elif button_hovered == btn_to_draw.text : state = "hover"
                    draw_keyboard_button(final_display_image, btn_to_draw, state)

                if program_state == "NORMAL":
                    cv2.rectangle(final_display_image, (50, 500), (1230, 600), (175, 0, 175), cv2.FILLED)
                    cv2.putText(final_display_image, finalText, (60, 580), cv2.FONT_HERSHEY_PLAIN, 5, (255, 255, 255), 5)
                
                elif program_state == "PASSWORD_ENTRY":
                    status_text_y = 470 
                    status_text_to_show = garden_action_text
                    if not status_text_to_show or "DANG NHAP THANH CONG!" in status_text_to_show :
                        status_text_to_show = f"Nhap mat khau. Con {MAX_ATTEMPTS - password_attempts} lan thu."
                    (status_text_w, status_text_h), _ = cv2.getTextSize(status_text_to_show, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
                    cv2.putText(final_display_image, status_text_to_show, ((1280 - status_text_w) // 2, status_text_y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    cv2.rectangle(final_display_image, (50, 500), (1230, 580), (175, 0, 175), cv2.FILLED)
                    cv2.putText(final_display_image, "Hay nhap mat khau de vao vuon", (60, 560), cv2.FONT_HERSHEY_PLAIN, 4, (255, 255, 255), 4)
                    cv2.rectangle(final_display_image, (50, 590), (1230, 640), (175, 0, 175), cv2.FILLED)
                    display_pass = "*" * len(password_input)
                    cv2.putText(final_display_image, display_pass, (60, 630), cv2.FONT_HERSHEY_PLAIN, 5, (255, 255, 255), 5)
                
                cv2.putText(final_display_image, hand_info_for_display, (10, 720 - 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

            cv2.imshow("Image", final_display_image)

        except Exception as e_loop:
            print(f"LỖI NGHIÊM TRỌNG TRONG VÒNG LẶP CHÍNH: {e_loop}")
            traceback.print_exc()
            break

        key_pressed = cv2.waitKey(1) & 0xFF
        if key_pressed == ord('q'): 
            print("INFO: Nhan phim 'q', dang thoat...")
            break
        # Loại bỏ phím 'j' để tránh vô tình tắt chế độ Jetson
        
finally:
    print("INFO: Dang thuc hien don dep cuoi cung...")
    if cap.isOpened():
        cap.release()
        print("INFO: Webcam da duoc giai phong.")
    cv2.destroyAllWindows()
    print("INFO: Tat ca cua so OpenCV da duoc dong.")
    
    if 'JETSON_MODE' in globals() and JETSON_MODE:
        if 'GPIO' in globals():
            print("INFO: Dang don dep GPIO...")
            try:
                set_leds_state(False)
                GPIO.cleanup()
                print("INFO: GPIO da duoc don dep.")
            except Exception as e_cleanup_gpio:
                print(f"LỖI khi don dep GPIO: {e_cleanup_gpio}")
        
        if ser and ser.is_open:
            print("INFO: Dang dong cong UART...")
            try:
                ser.close()
                print("INFO: Cong UART da duoc dong.")
            except Exception as e_cleanup_ser:
                print(f"LỖI khi dong cong UART: {e_cleanup_ser}")
            
    print("INFO: Chuong trinh da thoat.")