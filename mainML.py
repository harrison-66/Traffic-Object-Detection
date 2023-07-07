import re
import cv2
import numpy as np
from tensorflow.lite.python.interpreter import Interpreter
import csv
import datetime

CSV_FILE_PATH = 'traffic_data.csv'

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 360

def write_data_to_csv(data):
    with open(CSV_FILE_PATH, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(data)

def set_input_tensor(interpreter, image):
    """Sets the input tensor."""
    tensor_index = interpreter.get_input_details()[0]['index']
    input_tensor = interpreter.tensor(tensor_index)()[0]
    input_tensor[:, :] = np.expand_dims((image-255)/255, axis=0)

def get_output_tensor(interpreter, index):
    """Returns the output tensor at the given index."""
    output_details = interpreter.get_output_details()[index]
    tensor = np.squeeze(interpreter.get_tensor(output_details['index']))
    return tensor

def detect_objects(interpreter, image, threshold):
    """Returns a list of detection results, each a dictionary of object info."""
    set_input_tensor(interpreter, image)
    interpreter.invoke()
    # Get all output details
    boxes = get_output_tensor(interpreter, 0)
    classes = get_output_tensor(interpreter, 1)
    scores = get_output_tensor(interpreter, 2)
    count = 0  # Access the first element
    for i in range(9):
        if(boxes[i] >= 0.75):
            count += 1
        else:
            break

    results = []
    for i in range(count):
        if scores >= threshold:
            box_coordinates = classes[i]
            ymin, xmin, ymax, xmax = box_coordinates
            result = {
                'bounding_box': [ymin, xmin, ymax, xmax],
                'class_id': 'car',
                'score': scores
            }
            results.append(result)
    return results

def compare_rows(row, previous_row): # check if car has passed the middle of the frame
    currX = float(row[1])
    prevX = float(previous_row[1])
    if(currX > 320 and prevX < 320 and abs(currX - prevX) <= 80):
        return 1;
    if (currX < 320 and prevX > 320 and abs(currX - prevX) <= 80):
        return -1;
    return 0;

def append_to_csv(direction, timestamp, date):
    with open('final_data.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([direction, timestamp, date])

def delete_data_in_csv():
    with open(CSV_FILE_PATH, 'w') as file:
        file.truncate(0)

def process_csv():
    car_count_left_to_right = 0
    car_count_right_to_left = 0
    with open(CSV_FILE_PATH, 'r') as file:
        reader = csv.reader(file)
        # Initialize the previous_row
        previous_row = None
        # Iterate through the remaining rows
        for row in reader:
            add = 0
            # Compare with the previous row
            if previous_row is not None:
                add = compare_rows(row, previous_row)
                if(add == 1):
                    car_count_left_to_right += 1
                    append_to_csv("right", row[5], row[6])
                elif(add == -1):
                    car_count_right_to_left += 1
                    append_to_csv("left", row[5], row[6])
            # Update the previous_row variable
            previous_row = row

    print(f"Total cars (Left to Right): {car_count_left_to_right}")
    print(f"Total cars (Right to Left): {car_count_right_to_left}")
    print("Processed data saved to final_data.csv")
    delete_data_in_csv()

def main():
    label = "car"
    interpreter = Interpreter('detect.tflite')
    interpreter.allocate_tensors()
    _, input_height, input_width, _ = interpreter.get_input_details()[0]['shape']

    cap = cv2.VideoCapture(0)
    car_data = {}
    while cap.isOpened():
        ret, frame = cap.read()
        img = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), (320, 320))
        res = detect_objects(interpreter, img, 0.8)

        for result in res:
            box_coordinates = result['bounding_box']
            ymin, xmin, ymax, xmax = box_coordinates
            xmin = int(max(1, xmin * CAMERA_WIDTH))
            xmax = int(min(CAMERA_WIDTH, xmax * CAMERA_WIDTH))
            ymin = int(max(1, ymin * CAMERA_HEIGHT))
            ymax = int(min(CAMERA_HEIGHT, ymax * CAMERA_HEIGHT))

            car_id = None
            for existing_car_id, existing_car_data in car_data.items():
                existing_xmin = existing_car_data['xmin']
                existing_ymin = existing_car_data['ymin']
                existing_xmax = existing_car_data['xmax']
                existing_ymax = existing_car_data['ymax']
                
                if (
                    xmin >= existing_xmin and ymin >= existing_ymin and
                    xmax <= existing_xmax and ymax <= existing_ymax
                ):
                    car_id = existing_car_id
                    break

            if car_id is None:
                car_id = f'car_{len(car_data) + 1}'
                car_data[car_id] = {
                    'xmin': xmin,
                    'ymin': ymin,
                    'xmax': xmax,
                    'ymax': ymax
                }


            cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 3)
            cv2.putText(frame, result['class_id'], (xmin, min(ymax, CAMERA_HEIGHT-20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            date = datetime.datetime.now().strftime('%Y-%m-%d')
            data = [car_id, xmin, ymin, xmax, ymax, timestamp, date]
            write_data_to_csv(data)
        cv2.imshow('Car Detection', frame)

        if cv2.waitKey(10) & 0xFF == ord('q'):
            cap.release()
            cv2.destroyAllWindows()
# after loop breaks we want to exec on processData.py (pasted funcs over)
    process_csv()

if __name__ == "__main__":
    main()