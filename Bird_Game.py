import pygame
import time
import serial
import csv
import random
import os
import threading


pygame.init()

message_display_duration = 2
shot_times = []

arduino_port = 'COM4'
baud_rate = 115200

try:
    ser = serial.Serial(arduino_port, baud_rate, timeout=1)
    print(f"Connected to Arduino on {arduino_port}")
except Exception as e:
    print(f"Could not connect to Arduino: {e}")
    ser = None

# Global variable for force data file path


EXPERIMENT_SCREEN_WIDTH = 1920
EXPERIMENT_SCREEN_HEIGHT = 1080
BACKGROUND_COLOR = (255, 255, 255)
TEXT_COLOR = (0, 0, 0)

initial_intensity = 2
min_intensity = 2
max_intensity = 20
total_staircase_trials = 20
step_size = 1

total_experiment_trials = 1

GAME_SCREEN_WIDTH = 1920
GAME_SCREEN_HEIGHT = 1000
WALL_COLOR = (0, 0, 0)
FOOD_COLOR = (0, 255, 0)
BIRD_COLOR = (255, 165, 0)
BEAK_COLOR = (255, 0, 0)
BUTTON_COLOR = (0, 0, 255)
RED_HOLE_COLOR = (255, 0, 0)

wall_x = GAME_SCREEN_WIDTH // 3
wall_y = 50
wall_width = 50
wall_height = 600
hole_height = 100
hole_y = wall_y
hole_speed = 10

bird_x = wall_x + 200
bird_y = GAME_SCREEN_HEIGHT // 3

food_speed = 30
foods_in_motion = []
computer_food_in_motion = False
button_pressed = False
score = 0

last_shot_time = 0
last_computer_shot_time = 0
computer_shot_interval = 5
shot_interval = 3
hole_y_direction = 1
speed_setting = 'hard'
vibro_tactile_feedback = False
beak_open = True
beak_open_time = 0

current_level = 1
foods_fed = 0

total_trials = 10000
player_shot_percentage = 80
computer_shot_percentage = 20
player_shots = total_trials * player_shot_percentage // 100
computer_shots = total_trials * computer_shot_percentage // 100
current_trial = 0
remaining_player_shots = player_shots
remaining_computer_shots = computer_shots

message_text = ""
message_display_start_time = 0
message_display_duration = 2

screen = pygame.display.set_mode((GAME_SCREEN_WIDTH, GAME_SCREEN_HEIGHT))
pygame.display.set_caption("Vibration Experiment and Feed the Bird Game")

# Define the optimal window for a successful shot:
optimal_min = bird_y - hole_height  # lowest value for hole_y
optimal_max = bird_y  # highest value for hole_y
stop_event = threading.Event()  # Create a threading event to stop the thread safely

print(f"Optimal window for hole_y: {optimal_min} to {optimal_max}")

# This function will be used to continuously read force data from the Arduino
def read_force_data(force_data_filename):
    with open(force_data_filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'Force'])  # Write headers if file is empty

        while not stop_event.is_set():  # Run until stop_event is set
            if ser and ser.is_open and ser.in_waiting > 0:  # Check if serial is still open
                raw_data = ser.readline()  # Read raw data
                #print(f"Raw Data: {raw_data}")  # Debug print
                try:
                    force_value = raw_data.decode('utf-8').strip()
                    current_time = time.time() * 1000
                    writer.writerow([current_time, force_value])
                    #print(f"Force value: {force_value}, Time: {current_time:.2f} ms")
                except serial.SerialException as e:
                    print(f"SerialException: {e}. Exiting thread.")
                    break  # Exit the loop if serial error occurs
                except UnicodeDecodeError as e:
                    print(f"Decoding Error: {e}, Raw Data: {raw_data}")  # Debugging error
                time.sleep(0.1)  # Delay to avoid excessive reads
    print("Force data thread has stopped.")

def stop_recording():
    """Stops the force data recording thread safely."""
    print("Stopping force data recording...")
    stop_event.set()  # Signal the thread to stop

    # Wait for the thread to finish (small delay to ensure it stops)
    time.sleep(0.2)

    if ser and ser.is_open:
        ser.close()  # Close the serial connection safely
        print("Serial connection closed.")

def start_recording(subject_name):
    """ Starts a separate thread for recording force data using the subject's name. """
    sanitized_name = ''.join(char if char.isalnum() else '_' for char in subject_name)

    force_data_filename = f"force_data_{sanitized_name}.csv"

    # Check if a duplicate file exists and rename it if needed
    counter = 1
    while os.path.exists(force_data_filename):
        force_data_filename = f"force_data_{sanitized_name}_{counter}.csv"
        counter += 1

    # Start the thread to record force data
    force_thread = threading.Thread(target=read_force_data, args=(force_data_filename,))
    force_thread.daemon = True  # Ensure the thread closes when the main program exits
    force_thread.start()


def log_response(response=None, intensity=None, event_type=None, csv_writer=None, timestamp=None, score=None):

    if timestamp is None:
        timestamp = time.time() * 1000


    csv_writer.writerow([timestamp, response, intensity, event_type, score])


def send_vibration_intensity(intensity):
    if ser and ser.is_open:
        ser.write(f"{intensity}\n".encode())
        print(f"Sent intensity: {intensity}")


def display_text(screen, text, x, y):
    """Displays text on the Pygame screen."""
    font = pygame.font.SysFont(None, 36)
    lines = text.split('\n')
    for i, line in enumerate(lines):
        rendered_text = font.render(line, True, TEXT_COLOR)
        screen.blit(rendered_text, (x, y + i * 40))

def show_instructions(screen, instruction_text):

    screen.fill(BACKGROUND_COLOR)
    display_text(screen, instruction_text, 100, 100)
    display_text(screen, "Press any key to continue...", 100, 500)
    pygame.display.flip()

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN:
                waiting = False
        pygame.time.Clock().tick(30)


def get_subject_name(screen):

    name = ""
    input_active = True

    while input_active:
        screen.fill(BACKGROUND_COLOR)
        prompt = "Please enter your name:"
        display_text(screen, prompt, 100, 200)
        display_text(screen, name, 100, 300)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if name.strip() != "":
                        input_active = False
                elif event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                else:
                    # Limit name length to prevent excessively long filenames
                    if len(name) < 50:
                        # Only allow alphanumeric characters and spaces
                        if event.unicode.isalnum() or event.unicode == ' ':
                            name += event.unicode

        pygame.time.Clock().tick(30)

    return name.strip()


def run_staircase_procedure(csv_writer):

    global current_trial
    trial_count = 0
    intensity = initial_intensity
    last_trial_time = time.time()
    random_interval = random.randint(1, 10)


    reversals = []
    previous_direction = None
    reversal_limit = 10

    while trial_count < total_staircase_trials:
        screen.fill(BACKGROUND_COLOR)
        display_text(screen, f"Staircase Procedure: Trial {trial_count + 1}/{total_staircase_trials}", 150, 100)
        display_text(screen, "Press any foot key (Right, Up, Left) if you detected vibration.", 150, 300)
        display_text(screen, "Do NOT press any key if you did NOT detect vibration.", 150, 350)

        pygame.display.flip()

        current_time = time.time()

        if current_time - last_trial_time >= random_interval:
            send_vibration_intensity(intensity)
            trial_count += 1
            last_trial_time = current_time
            random_interval = random.randint(1, 10)

            response = 0
            response_start_time = time.time()
            response_window = 5

            while time.time() - response_start_time < response_window:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        exit()
                    elif event.type == pygame.KEYDOWN:
                        if event.key in [pygame.K_RIGHT, pygame.K_UP, pygame.K_LEFT]:
                            response = 1
                            break

                if response == 1:
                    break

                pygame.display.flip()
                pygame.time.Clock().tick(30)

            log_response(response, intensity, "Staircase Procedure", csv_writer)

            if response == 1:
                new_intensity = max(min_intensity, intensity - step_size)  # Decrease intensity
                direction = "down"
            else:
                new_intensity = min(max_intensity, intensity + step_size)  # Increase intensity
                direction = "up"

            if previous_direction and direction != previous_direction:
                reversals.append(intensity)
                print(f"Reversal at intensity: {intensity}")

            previous_direction = direction
            intensity = new_intensity

    if len(reversals) >= reversal_limit:
        threshold = sum(reversals[-reversal_limit:]) / reversal_limit
    elif reversals:
        threshold = sum(reversals) / len(reversals)
    else:
        threshold = intensity

    screen.fill(BACKGROUND_COLOR)
    display_text(screen, "Staircase Procedure Completed!", 200, 250)
    display_text(screen, f"Estimated Absolute Threshold: {threshold:.2f}", 200, 300)
    display_text(screen, "Press any key to continue to Experiments.", 150, 350)
    pygame.display.flip()

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN:
                waiting = False
        pygame.display.flip()
        pygame.time.Clock().tick(30)

    return threshold

def draw_wall_with_hole(screen, wall_x, wall_y, hole_y, hole_height):
    pygame.draw.rect(screen, WALL_COLOR, (wall_x, wall_y, wall_width, wall_height))
    pygame.draw.rect(screen, RED_HOLE_COLOR, (wall_x, hole_y, wall_width, hole_height))


def draw_bird(screen, x, y, beak_open):
    pygame.draw.ellipse(screen, BIRD_COLOR, (x - 30, y - 20, 60, 40))
    pygame.draw.circle(screen, (0, 0, 0), (x - 15, y - 10), 5)
    if beak_open:
        pygame.draw.polygon(screen, BEAK_COLOR, [(x - 30, y), (x - 50, y - 10), (x - 50, y + 10)])
    else:
        pygame.draw.polygon(screen, BEAK_COLOR, [(x - 30, y), (x - 40, y - 5), (x - 40, y + 5)])

def update_food_position():
    global foods_in_motion, score, message_text, foods_fed, current_level, message_display_duration
    global game_over, running_game

    for food in foods_in_motion[:]:
        pygame.draw.circle(screen, FOOD_COLOR, (food['x'], food['y']), 10)
        food['x'] += food_speed

        if food['x'] >= wall_x:
            if not food['passing_hole'] and hole_y <= food['y'] <= hole_y + hole_height:
                food['passing_hole'] = True
            elif not food['passing_hole'] and food['player_shot']:
                message_text = "Hit the Wall!"
                score -= 1
                foods_in_motion.remove(food)

        if food['x'] >= bird_x - 30:
            if food['player_shot']:
                if beak_open:
                    message_text = "Fed the Bird!"
                    score += 10
                    foods_fed += 1
                else:
                    message_text = "Missed the Bird!"
                    score -= 5
            else:
                if beak_open:
                    message_text = "Computer Fed the Bird!"
                    score -= 5
                else:
                    message_text = "Player Blocked the Bird!"
                    score += 5
            foods_in_motion.remove(food)


    # Stop the game after feeding 300 times
    if foods_fed == 50:
        foods_fed = 0
        if current_level == 1:
            current_level += 1
            level_up_to_2()
        elif current_level == 2:
            current_level += 1
            level_up_to_3()
        elif current_level == 3:
            message_text = f"Game Over! Final Score: {score}"
            print(message_text)  # Debugging
            display_text(screen, message_text, 400, 300)

            pygame.display.flip()  # Update the display to show the final score
            pygame.time.delay(3000)  # Keep the final score on screen for 3 seconds

            game_over = True
            running_game = False
            return

def level_up_to_2():
    global hole_speed, message_text, message_display_start_time, food_speed, message_display_duration
    message_text = "Congratulations! Level 2: Speeding Up!"
    #pygame.mixer.Sound.play(congratulations_sound)  # Play the congratulatory sound
    message_display_start_time = time.time()
    message_display_duration = 5  # Increase display duration for level-up message
    hole_speed += 4  # Increase hole speed to make it harder
    food_speed += 2  # Optionally increase food speed as well
    print("Level up: Speeding up the hole")

def level_up_to_3():
    global hole_height, message_text, message_display_start_time, message_display_duration
    message_text = "Congratulations! Level 3: Narrowing the Hole!"
    # pygame.mixer.Sound.play(congratulations_sound)  # Play the congratulatory sound
    message_display_start_time = time.time()
    message_display_duration = 5  # Increase display duration for level-up message
    hole_height -= 10  # Reduce the height of the hole to make it harder
    print("Level up: Narrowing the hole")
def handle_player_shoot(csv_writer=None, threshold_intensity=4):
    global foods_in_motion, last_shot_time, vibro_tactile_feedback, foods_fed, current_trial, remaining_player_shots, beak_open
    global shot_times, vibration_times

    food_x = 100
    food_y = bird_y
    foods_in_motion.append({'x': food_x, 'y': food_y, 'passing_hole': False, 'player_shot': True})

    current_time = time.time() * 1000
    shot_times.append(current_time)
    last_shot_time = current_time
    vibro_tactile_feedback = True

    if len(shot_times) > 1:
        interval = shot_times[-1] - shot_times[-2]
        predicted_next_shot = shot_times[-1] + interval

        vibration_time = predicted_next_shot - 50

        vibration_times.append(vibration_time)


        print(f"Player shot at: {current_time} ms")
        print(f"Predicted next shot at: {predicted_next_shot} ms")
        print(f"Vibration scheduled at: {vibration_time} ms before predicted shot")
    else:
        print(f"Player shot at: {current_time} ms")


def handle_computer_shoot(csv_writer=None):
    global foods_in_motion, last_computer_shot_time, remaining_computer_shots
    current_time = time.time()*1000
    if current_time - last_computer_shot_time >= computer_shot_interval and remaining_computer_shots > 0:
        food_x = 100
        food_y = bird_y
        foods_in_motion.append({'x': food_x, 'y': food_y, 'passing_hole': False, 'player_shot': False})
        last_computer_shot_time = current_time
        remaining_computer_shots -= 1
        print(f"Computer shot at {current_time} ms")

vibration_times = []
last_shot_time = 0
cooldown_time = 700


def run_game(csv_writer, threshold_intensity):
    global beak_open, hole_speed, hole_height, hole_y, hole_y_direction, message_text
    global score, foods_fed, current_level, food_speed, current_trial, remaining_player_shots, remaining_computer_shots, game_over
    global vibration_times, message_display_duration, last_shot_time, cooldown_time



    game_over = False
    running_game = True

    print("Game started. Press '1' to shoot.")

    while running_game:
        screen.fill(BACKGROUND_COLOR)

        if game_over:
            display_text(screen, message_text, 400, 300)
            pygame.display.flip()
            pygame.time.wait(3000)
            running_game = False
            continue

        current_time = time.time() * 1000

        # Process scheduled vibrations
        if vibration_times and current_time >= vibration_times[0]:
            send_vibration_intensity(threshold_intensity)
            log_response(None, threshold_intensity, "VibrationSent", csv_writer, timestamp=current_time)
            print(f"Vibration triggered at {current_time:.0f} ms")
            vibration_times.pop(0)

        shot_occurred = False  # Flag to detect if a shot event occurs this frame

        # Process events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running_game = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RIGHT, pygame.K_UP, pygame.K_LEFT):
                    log_response(1, threshold_intensity, "FootPedalPress", csv_writer, timestamp=current_time)
                elif event.key in (pygame.K_1, pygame.K_KP1):
                    if current_time - last_shot_time >= cooldown_time:
                        # Compute travel time and predicted hole position with bouncing logic:
                        food_start_x = 100  # where food is shot from
                        T_travel = (wall_x - food_start_x) / food_speed  # in seconds
                        lower_bound = wall_y
                        upper_bound = wall_y + wall_height - hole_height
                        L = upper_bound - lower_bound
                        # Compute current effective position (relative to lower_bound)
                        x0_prime = hole_y - lower_bound
                        # Displacement during travel (including direction)
                        s = hole_speed * T_travel * hole_y_direction
                        # Reflect the new position within the allowed range:
                        x_eff = ((x0_prime + s) % (2 * L))
                        if x_eff > L:
                            predicted_hole_y = lower_bound + (2 * L - x_eff)
                        else:
                            predicted_hole_y = lower_bound + x_eff

                        # Define the optimal window:
                        optimal_min = bird_y - hole_height
                        optimal_max = bird_y
                        optimal_flag = (optimal_min <= predicted_hole_y <= optimal_max)

                        # Log the player's shot with optimal moment info:
                        event_detail = (f"PlayerShoot; current_hole_y={hole_y:.2f}; "
                                        f"predicted_hole_y={predicted_hole_y:.2f}; optimal={optimal_flag}")
                        score_detail= (f"Score={score:.2f}; ")
                        log_response(None, threshold_intensity, event_detail, csv_writer, timestamp=current_time, score=score_detail)
                        print(f"Player shot at {current_time:.0f} ms, current hole_y: {hole_y:.2f}, predicted hole_y: {predicted_hole_y:.2f}, optimal: {optimal_flag}")

                        handle_player_shoot(csv_writer, threshold_intensity)
                        current_trial += 1
                        remaining_player_shots -= 1
                        last_shot_time = current_time
                        shot_occurred = True
                    else:
                        print("Shot ignored. Please wait before shooting again.")
                elif event.key in (pygame.K_3, pygame.K_KP3):
                    beak_open = False
                    log_response(None, None, "CloseMouth", csv_writer, timestamp=current_time)
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_3, pygame.K_KP3):
                    beak_open = True

        # --- Update the hole position with boundary check and computer shoot ---
        hole_y += hole_speed * hole_y_direction
        if hole_y <= wall_y:
            hole_y_direction = 1
        elif hole_y + hole_height >= wall_y + wall_height:
            hole_y_direction = -1
            handle_computer_shoot(csv_writer)
            log_response(None, threshold_intensity, "ComputerShoot", csv_writer, timestamp=current_time)

        # --- Calculate predicted hole position with bouncing logic ---
        food_start_x = 100  # where food is shot from
        T_travel = (wall_x - food_start_x) / food_speed  # in seconds
        lower_bound = wall_y
        upper_bound = wall_y + wall_height - hole_height
        L = upper_bound - lower_bound
        x0_prime = hole_y - lower_bound
        s = hole_speed * T_travel * hole_y_direction
        x_eff = ((x0_prime + s) % (2 * L))
        if x_eff > L:
            predicted_hole_y = lower_bound + (2 * L - x_eff)
        else:
            predicted_hole_y = lower_bound + x_eff

        optimal_min = bird_y - hole_height
        optimal_max = bird_y

        # Log an optimal moment if no shot occurred this frame and predicted hole is optimal:
        if (not shot_occurred) and (optimal_min <= predicted_hole_y <= optimal_max):
            log_response("NoShot", threshold_intensity,
                         f"OptimalMoment; current_hole_y={hole_y:.2f}; predicted_hole_y={predicted_hole_y:.2f}",
                         csv_writer, timestamp=time.time() * 1000)
            print(f"Optimal moment logged: current_hole_y={hole_y:.2f}, predicted_hole_y={predicted_hole_y:.2f}")

        # --- Draw game objects ---
        draw_wall_with_hole(screen, wall_x, wall_y, hole_y, hole_height)
        draw_bird(screen, bird_x, bird_y, beak_open)
        pygame.draw.rect(screen, BUTTON_COLOR, (50, 333, 100, 50))
        display_text(screen, "Shoot", 60, 343)
        update_food_position()
        display_text(screen, f"Score: {score}", 1000, 50)

        if message_text:
            display_text(screen, message_text, 200, 50)
            if time.time() - message_display_start_time > message_display_duration:
                message_text = ""
                message_display_duration = 2

        pygame.display.flip()
        pygame.time.Clock().tick(30)

    if ser:
        ser.close()

def main():
    global current_trial, remaining_player_shots, remaining_computer_shots





    subject_name = get_subject_name(screen)
    print(f"Subject Name: {subject_name}")

    # Start recording force data
    start_recording(subject_name)
    time.sleep(2)

    sanitized_name = ''.join(char if char.isalnum() else '_' for char in subject_name)


    csv_filename = f"experiment_responses_{sanitized_name}.csv"


    if os.path.exists(csv_filename):

        counter = 1
        while os.path.exists(f"experiment_responses_{sanitized_name}_{counter}.csv"):
            counter += 1
        csv_filename = f"experiment_responses_{sanitized_name}_{counter}.csv"

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Timestamp', 'Response', 'Intensity', 'Experiment'])

        staircase_instructions = (
            "Welcome to the Vibration Detection Experiment!\n\n"
            "In the first part, you will undergo a Staircase Procedure to determine your vibration detection threshold.\n"
            "A vibration will be sent at varying intensities.\n"
            "Press any foot key (Right, Up, Left) if you detect the vibration.\n"
            "Do NOT press any key if you do NOT detect the vibration.\n\n"
            "Please ensure you are in a comfortable position and can clearly feel the vibrations.\n"
            "Press any key to begin the Staircase Procedure."
        )
        show_instructions(screen, staircase_instructions)

        threshold_intensity = run_staircase_procedure(writer)

        print(f"Determined Absolute Threshold: {threshold_intensity:.2f}")

    game_instructions = (
        "Game: Feed the Bird\n\n"
        "In this game, you will feed the bird by shooting food items.\n"
        "Press key '1' to shoot if you want to feed the bird.\n"
        "Press key '3' to close the bird's mouth.\n"
        "Continue tapping any foot keys (Right, Up, Left) to respond to vibrations.\n\n"
        "Press any key to begin the Game."
    )
    show_instructions(screen, game_instructions)

    with open(csv_filename, mode='a', newline='') as file:
        writer = csv.writer(file)

        run_game(writer, threshold_intensity)

    screen.fill(BACKGROUND_COLOR)
    display_text(screen, f"Your responses have been saved to '{csv_filename}'.", 150, 250)
    display_text(screen, "Press any key to exit.", 200, 300)
    pygame.display.flip()


    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN:
                waiting = False
        pygame.display.flip()
        pygame.time.Clock().tick(30)

    if ser:
        ser.close()


    pygame.quit()


if __name__ == "__main__":
    main()