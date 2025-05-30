import pygame
import random
import numpy
import math

pygame.init()

# Explicitly initialize mixer with correct settings
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512) # Stereo, larger buffer

# Game window
WIDTH, HEIGHT = 600, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Cat-san's Kong Tribute!")

# --- Sound Generation ---
SAMPLE_RATE = 44100

def generate_beep_sound(freq, duration_ms, volume=0.3, shape='sine'):
    duration_sec = duration_ms / 1000.0
    t = numpy.linspace(0, duration_sec, int(SAMPLE_RATE * duration_sec), False)
    if shape == 'sine':
        wave = numpy.sin(freq * t * 2 * numpy.pi)
    elif shape == 'square':
        wave = numpy.sign(numpy.sin(freq * t * 2 * numpy.pi))
    elif shape == 'sawtooth':
        # Simple sawtooth: t * freq * 2 creates a ramp from 0 to 2*duration_sec*freq
        # % 2 maps it to 0-2 range, then -1 maps to -1 to 1 range.
        wave = ((t * freq) % 1.0) * 2 - 1 # Corrected sawtooth
    else: # Default to sine
        wave = numpy.sin(freq * t * 2 * numpy.pi)

    # Simple fade out to avoid clicking (last 5ms)
    fade_out_samples = int(SAMPLE_RATE * 0.005)
    if len(wave) > fade_out_samples * 2: # Ensure wave is long enough for fade
        fade_curve = numpy.linspace(1, 0, fade_out_samples)
        wave[-fade_out_samples:] *= fade_curve

    sound_data = (wave * 32767 * volume).astype(numpy.int16)
    # Pygame's Sound object will handle mono-to-stereo conversion if mixer is stereo
    return pygame.mixer.Sound(buffer=sound_data)


jump_sound = generate_beep_sound(660, 100, volume=0.25, shape='sine')

duh_sounds = []
for _ in range(4): # DUH DUH DUH DUH
    duh_sounds.append(generate_beep_sound(130, 150, volume=0.35, shape='square'))
duh_sounds.append(generate_beep_sound(110, 250, volume=0.4, shape='square')) # Final DHH lower and longer

player_hit_sound = generate_beep_sound(200, 250, volume=0.3, shape='sawtooth')
level_win_sound = generate_beep_sound(880, 500, volume=0.3, shape='sine') # A nice A5
game_over_sound = generate_beep_sound(100, 800, volume=0.4, shape='sawtooth')


# Colors
BLACK = (0,0,0)
WHITE = (255,255,255)
DK_RED = (200,0,0)
PLAYER_BLUE = (100, 100, 255)
PAULINE_PINK = (255, 150, 200)
GIRDER_BROWN = (139, 69, 19)
LADDER_CYAN = (0, 180, 180)
BARREL_ORANGE = (200, 100, 20) # Slightly adjusted
OIL_DRUM_BLUE = (50, 50, 150)
TEXT_YELLOW = (255,255,0)
TEXT_GREEN = (0,200,0) # Darker green
TEXT_RED = (255,50,50)


# --- Game Constants ---
GRAVITY = 0.7 # Slightly less floaty
PLAYER_JUMP_STRENGTH = -15 # Matched with gravity
PLAYER_SPEED = 3.5
PLAYER_CLIMB_SPEED = 2.5
BARREL_ROLL_SPEED_BASE = 2.2
INITIAL_LIVES = 3
GIRDER_VISUAL_HEIGHT = 15

# Helper function to get surface Y on a girder
def get_girder_surface_y(entity_x_or_rect, girder_data):
    if isinstance(entity_x_or_rect, pygame.Rect):
        x_coord = entity_x_or_rect.centerx
    else:
        x_coord = entity_x_or_rect

    g_rect_span = girder_data['rect'] # This rect is for horizontal span and visual top Y
    clamped_x = max(g_rect_span.left, min(x_coord, g_rect_span.right))
    relative_x = clamped_x - g_rect_span.left

    if g_rect_span.width == 0:
        return girder_data['y_start']

    percentage_across = relative_x / g_rect_span.width
    surface_y = girder_data['y_start'] + (girder_data['y_end'] - girder_data['y_start']) * percentage_across
    return surface_y

# --- Level Definitions ---
g_level_girders = []
g_level_ladders = []
g_kong_rect = pygame.Rect(0,0,1,1)
g_goal_rect = pygame.Rect(0,0,1,1)
g_oil_drum_rect = pygame.Rect(0,0,1,1)
g_current_barrel_spawn_rate = 2500
g_kong_platform_idx_for_barrel_spawn = 0
g_current_barrel_roll_speed = BARREL_ROLL_SPEED_BASE

def define_level_1_elements(width, height):
    girders = []
    gh = GIRDER_VISUAL_HEIGHT

    y0_surf = height - 60
    girders.append({'id': 'G0', 'rect': pygame.Rect(0, y0_surf - gh, width, gh), 'y_start': y0_surf, 'y_end': y0_surf})
    y1_r_surf = height - 180; y1_l_surf = y1_r_surf - 35
    girders.append({'id': 'G1', 'rect': pygame.Rect(50, y1_l_surf - gh, width - 100, gh), 'y_start': y1_l_surf, 'y_end': y1_r_surf})
    y2_l_surf = height - 300; y2_r_surf = y2_l_surf - 35
    girders.append({'id': 'G2', 'rect': pygame.Rect(50, y2_r_surf - gh, width - 100, gh), 'y_start': y2_l_surf, 'y_end': y2_r_surf})
    y3_r_surf = height - 420; y3_l_surf = y3_r_surf - 35
    girders.append({'id': 'G3', 'rect': pygame.Rect(50, y3_l_surf - gh, width - 100, gh), 'y_start': y3_l_surf, 'y_end': y3_r_surf})
    y4_l_surf = height - 540; y4_r_surf = y4_l_surf - 35
    girders.append({'id': 'G4_KONG', 'rect': pygame.Rect(50, y4_r_surf - gh, width - 100, gh), 'y_start': y4_l_surf, 'y_end': y4_r_surf})
    KONG_PLATFORM_INDEX = 4

    kong_size = (55, 45)
    kong_x = 70
    kong_stand_y = get_girder_surface_y(kong_x + kong_size[0]//2, girders[KONG_PLATFORM_INDEX])
    kong_rect = pygame.Rect(kong_x, kong_stand_y - kong_size[1], kong_size[0], kong_size[1])

    pauline_plat_y_surf = y4_l_surf - 100
    girders.append({'id': 'TOP', 'rect': pygame.Rect(width // 2 - 70, pauline_plat_y_surf - gh, 140, gh), 'y_start': pauline_plat_y_surf, 'y_end': pauline_plat_y_surf})
    GOAL_PLATFORM_INDEX = 5
    pauline_size = (25,35)
    goal_rect = pygame.Rect(width // 2 - pauline_size[0]//2, pauline_plat_y_surf - pauline_size[1], pauline_size[0], pauline_size[1])

    ladders = []
    lw = 18
    lad_x = girders[1]['rect'].right - 30
    lad_top_y = get_girder_surface_y(lad_x, girders[1])
    lad_bottom_y = get_girder_surface_y(lad_x, girders[0])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_top_y, lw, lad_bottom_y - lad_top_y))

    lad_x = girders[1]['rect'].centerx - 90
    lad_bottom_y = get_girder_surface_y(lad_x, girders[1])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_bottom_y - 50, lw, 50)) # Broken ladder

    lad_x = girders[2]['rect'].left + 30
    lad_top_y = get_girder_surface_y(lad_x, girders[2])
    lad_bottom_y = get_girder_surface_y(lad_x, girders[1])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_top_y, lw, lad_bottom_y - lad_top_y))

    lad_x = girders[3]['rect'].right - 30
    lad_top_y = get_girder_surface_y(lad_x, girders[3])
    lad_bottom_y = get_girder_surface_y(lad_x, girders[2])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_top_y, lw, lad_bottom_y - lad_top_y))

    lad_x = girders[KONG_PLATFORM_INDEX]['rect'].left + 30
    lad_top_y = get_girder_surface_y(lad_x, girders[KONG_PLATFORM_INDEX])
    lad_bottom_y = get_girder_surface_y(lad_x, girders[3])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_top_y, lw, lad_bottom_y - lad_top_y))

    lad_x = girders[GOAL_PLATFORM_INDEX]['rect'].centerx
    lad_top_y = get_girder_surface_y(lad_x, girders[GOAL_PLATFORM_INDEX])
    lad_bottom_y = get_girder_surface_y(lad_x, girders[KONG_PLATFORM_INDEX])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_top_y, lw, lad_bottom_y - lad_top_y))

    oil_drum_size = (35,35)
    oil_drum_x = 40
    oil_drum_rect = pygame.Rect(oil_drum_x, get_girder_surface_y(oil_drum_x + oil_drum_size[0]//2, girders[0]) - oil_drum_size[1], oil_drum_size[0], oil_drum_size[1])

    # Adjust visual rects' top based on y_start/y_end for sloped girders
    for g in girders:
        g['rect'].top = min(g['y_start'], g['y_end']) - gh if g['y_start'] != g['y_end'] else g['y_start'] - gh
        g['rect'].height = gh + abs(g['y_start'] - g['y_end']) if g['y_start'] != g['y_end'] else gh


    return {
        "name": "25m - Rampage",
        "girders_def": girders, "ladders_def": ladders, "kong_rect_def": kong_rect,
        "goal_rect_def": goal_rect, "oil_drum_rect_def": oil_drum_rect,
        "player_start_x_offset": width / 10, "player_start_girder_idx": 0,
        "barrel_spawn_rate": 2600, "kong_platform_idx_ref": KONG_PLATFORM_INDEX,
        "barrel_roll_speed": BARREL_ROLL_SPEED_BASE,
    }

def define_level_2_elements(width, height):
    girders = []
    gh = GIRDER_VISUAL_HEIGHT

    y0_surf = height - 60
    girders.append({'id': 'L2G0', 'rect': pygame.Rect(0, y0_surf - gh, width, gh), 'y_start': y0_surf, 'y_end': y0_surf})
    y1_surf = height - 200
    girders.append({'id': 'L2G1', 'rect': pygame.Rect(width * 0.1, y1_surf - gh, width * 0.8, gh), 'y_start': y1_surf, 'y_end': y1_surf})
    y2_surf = height - 360
    girders.append({'id': 'L2G2_KONG', 'rect': pygame.Rect(width * 0.05, y2_surf - gh, width * 0.9, gh), 'y_start': y2_surf, 'y_end': y2_surf})
    KONG_PLATFORM_INDEX = 2
    y3_surf = height - 520
    girders.append({'id': 'L2G3_PAULINE', 'rect': pygame.Rect(width // 2 - 80, y3_surf - gh, 160, gh), 'y_start': y3_surf, 'y_end': y3_surf})
    GOAL_PLATFORM_INDEX = 3

    kong_size = (55, 45)
    kong_x = width * 0.12
    kong_stand_y = get_girder_surface_y(kong_x + kong_size[0]//2, girders[KONG_PLATFORM_INDEX])
    kong_rect = pygame.Rect(kong_x, kong_stand_y - kong_size[1], kong_size[0], kong_size[1])

    pauline_size = (25,35)
    goal_rect = pygame.Rect(girders[GOAL_PLATFORM_INDEX]['rect'].centerx - pauline_size[0]//2,
                            y3_surf - pauline_size[1], pauline_size[0], pauline_size[1])

    ladders = []
    lw = 18
    lad_x = girders[1]['rect'].left + 40
    lad_top_y = get_girder_surface_y(lad_x, girders[1]); lad_bottom_y = get_girder_surface_y(lad_x, girders[0])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_top_y, lw, lad_bottom_y - lad_top_y))

    lad_x = girders[1]['rect'].centerx - 50 # Left-center ladder G1-G2
    lad_top_y = get_girder_surface_y(lad_x, girders[2]); lad_bottom_y = get_girder_surface_y(lad_x, girders[1])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_top_y, lw, lad_bottom_y - lad_top_y))

    lad_x = girders[1]['rect'].centerx + 50 # Right-center ladder G1-G2
    lad_top_y = get_girder_surface_y(lad_x, girders[2]); lad_bottom_y = get_girder_surface_y(lad_x, girders[1])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_top_y, lw, lad_bottom_y - lad_top_y))


    lad_x = girders[GOAL_PLATFORM_INDEX]['rect'].centerx
    lad_top_y = get_girder_surface_y(lad_x, girders[GOAL_PLATFORM_INDEX]); lad_bottom_y = get_girder_surface_y(lad_x, girders[KONG_PLATFORM_INDEX])
    ladders.append(pygame.Rect(lad_x - lw//2, lad_top_y, lw, lad_bottom_y - lad_top_y))

    oil_drum_size = (35,35)
    oil_drum_x = width - 70
    oil_drum_rect = pygame.Rect(oil_drum_x, get_girder_surface_y(oil_drum_x + oil_drum_size[0]//2, girders[0]) - oil_drum_size[1], oil_drum_size[0], oil_drum_size[1])

    for g in girders: # Ensure visual rects are set correctly for flat girders too
        g['rect'].top = g['y_start'] - gh
        g['rect'].height = gh

    return {
        "name": "50m - Factory Floor",
        "girders_def": girders, "ladders_def": ladders, "kong_rect_def": kong_rect,
        "goal_rect_def": goal_rect, "oil_drum_rect_def": oil_drum_rect,
        "player_start_x_offset": width * 0.85, "player_start_girder_idx": 0,
        "barrel_spawn_rate": 2300, "kong_platform_idx_ref": KONG_PLATFORM_INDEX,
        "barrel_roll_speed": BARREL_ROLL_SPEED_BASE * 1.15,
    }

levels_data_generators = [define_level_1_elements, define_level_2_elements]
current_level_index = 0

# --- Player Initialization ---
player_rect = pygame.Rect(0,0, 28, 28)
player_y_velocity = 0
player_on_ground = False
player_on_ladder = False
player_climbing = False
player_lives = INITIAL_LIVES
score = 0

# --- Barrels ---
barrels = []
BARREL_EVENT = pygame.USEREVENT + 1
BARREL_SIZE = 22


def reset_player_position_for_level_start_or_death():
    global player_y_velocity, player_on_ground, player_on_ladder, player_climbing, player_rect
    # No need to call level_elements = levels_data_generators[current_level_index](WIDTH, HEIGHT) here
    # as g_level_girders is already populated by load_level
    start_girder_idx = levels_data_generators[current_level_index](WIDTH,HEIGHT)["player_start_girder_idx"]
    start_x_offset = levels_data_generators[current_level_index](WIDTH,HEIGHT)["player_start_x_offset"]
    start_girder = g_level_girders[start_girder_idx]
    player_rect.midbottom = (start_x_offset, get_girder_surface_y(start_x_offset, start_girder))
    player_y_velocity = 0
    player_on_ground = True
    player_on_ladder = False
    player_climbing = False

def load_level(level_idx):
    global g_level_girders, g_level_ladders, g_kong_rect, g_goal_rect, g_oil_drum_rect
    global g_current_barrel_spawn_rate, g_kong_platform_idx_for_barrel_spawn, g_current_barrel_roll_speed
    global current_level_index, game_state, barrels, intro_stage, intro_timer, intro_sound_played_this_stage
    global is_level_won

    if level_idx >= len(levels_data_generators):
        game_state = STATE_VICTORY
        # game_over_sound.play() # Or a victory fanfare
        return

    current_level_index = level_idx
    level_data_func = levels_data_generators[level_idx]
    level_elements = level_data_func(WIDTH, HEIGHT) # Call to get all definitions

    g_level_girders = level_elements["girders_def"]
    g_level_ladders = level_elements["ladders_def"]
    g_kong_rect = level_elements["kong_rect_def"]
    g_goal_rect = level_elements["goal_rect_def"]
    g_oil_drum_rect = level_elements["oil_drum_rect_def"]
    g_current_barrel_spawn_rate = level_elements["barrel_spawn_rate"]
    g_kong_platform_idx_for_barrel_spawn = level_elements["kong_platform_idx_ref"]
    g_current_barrel_roll_speed = level_elements["barrel_roll_speed"]

    pygame.time.set_timer(BARREL_EVENT, 0)
    pygame.time.set_timer(BARREL_EVENT, g_current_barrel_spawn_rate)

    reset_player_position_for_level_start_or_death() # Player pos depends on loaded girders
    barrels.clear()
    is_level_won = False

    game_state = STATE_INTRO
    intro_stage = 0
    intro_timer = pygame.time.get_ticks()
    intro_sound_played_this_stage = False # Reset for the new intro sequence


# --- Game States ---
STATE_INTRO = 0
STATE_PLAYING = 1
STATE_GAME_OVER_LOST = 2
STATE_VICTORY = 3
game_state = STATE_INTRO

is_level_won = False

intro_timer = 0
intro_stage = 0
# Durations for "LEVEL X", "READY!", "GO!" + final brief pause before play starts
intro_stage_durations = [1200, 1000, 800, 200]
intro_texts = ["LEVEL X", "READY!", "GO!!", ""] # Last one is for the pause
intro_sound_played_this_stage = False # Tracks if sound for current stage has been played


# Fonts
default_font_name = "Arial" # Fallback
title_font_size = 36
score_font_size = 20
message_font_size = 28
small_message_font_size = 16

try:
    title_font = pygame.font.Font("PressStart2P.ttf", title_font_size)
    score_font = pygame.font.Font("PressStart2P.ttf", score_font_size)
    message_font = pygame.font.Font("PressStart2P.ttf", message_font_size)
    small_message_font = pygame.font.Font("PressStart2P.ttf", small_message_font_size)
    print("'PressStart2P.ttf' font loaded successfully!")
except FileNotFoundError:
    print(f"INFO: 'PressStart2P.ttf' not found. Using '{default_font_name}' as fallback.")
    title_font = pygame.font.SysFont(default_font_name, title_font_size + 8, bold=True) # Arial needs to be bigger
    score_font = pygame.font.SysFont(default_font_name, score_font_size + 4)
    message_font = pygame.font.SysFont(default_font_name, message_font_size + 6)
    small_message_font = pygame.font.SysFont(default_font_name, small_message_font_size + 4)


# --- Main Game Loop ---
clock = pygame.time.Clock()
running = True
load_level(current_level_index)

while running:
    dt = clock.tick(60)
    current_time = pygame.time.get_ticks()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if game_state == STATE_PLAYING and event.type == BARREL_EVENT:
            if g_kong_platform_idx_for_barrel_spawn < len(g_level_girders):
                kong_girder = g_level_girders[g_kong_platform_idx_for_barrel_spawn]
                spawn_offset_x = g_kong_rect.width * 0.6 # Spawn slightly away from Kong's edge
                barrel_start_x = g_kong_rect.centerx + spawn_offset_x if random.choice([True,False]) else g_kong_rect.centerx - spawn_offset_x

                actual_start_y_surface = get_girder_surface_y(barrel_start_x, kong_girder)

                barrel_initial_dir = 0
                if kong_girder['y_start'] == kong_girder['y_end']: # Flat
                    barrel_initial_dir = 1 if barrel_start_x > g_kong_rect.centerx else -1
                elif kong_girder['y_start'] < kong_girder['y_end']: # Slopes down to right (y_start is higher value on screen)
                     barrel_initial_dir = 1 # Roll right
                else: # Slopes down to left
                     barrel_initial_dir = -1 # Roll left

                barrels.append({
                    'rect': pygame.Rect(barrel_start_x - BARREL_SIZE//2, actual_start_y_surface - BARREL_SIZE, BARREL_SIZE, BARREL_SIZE),
                    'dir': barrel_initial_dir, 'y_vel': 0,
                    'on_girder_id': kong_girder['id'], 'roll_angle': 0
                })

        if event.type == pygame.KEYDOWN:
            if game_state == STATE_PLAYING:
                if (event.key == pygame.K_SPACE or event.key == pygame.K_UP or event.key == pygame.K_w) and player_on_ground and not player_on_ladder:
                    player_y_velocity = PLAYER_JUMP_STRENGTH
                    jump_sound.play()
                    player_on_ground = False
            elif (game_state == STATE_GAME_OVER_LOST or game_state == STATE_VICTORY) and event.key == pygame.K_r:
                player_lives = INITIAL_LIVES; score = 0; current_level_index = 0
                load_level(current_level_index) # Resets state to INTRO

    keys = pygame.key.get_pressed()

    if game_state == STATE_INTRO:
        intro_texts[0] = f"LEVEL {current_level_index + 1}" # Update for current level
        if not intro_sound_played_this_stage:
            if intro_stage == 0 and duh_sounds[0]: duh_sounds[0].play() # Sound for "LEVEL X" (first 'duh')
            elif intro_stage == 1 and duh_sounds[1]: duh_sounds[1].play() # Sound for "READY!" (second 'duh')
            elif intro_stage == 2 and duh_sounds[3]: duh_sounds[3].play() # Sound for "GO!!" (more impactful 'duh')
            intro_sound_played_this_stage = True

        if current_time - intro_timer > intro_stage_durations[intro_stage]:
            intro_timer = current_time
            intro_stage += 1
            intro_sound_played_this_stage = False # Reset for next stage sound
            if intro_stage >= len(intro_texts):
                game_state = STATE_PLAYING
                intro_stage = 0 # Reset for next time intro is called

    elif game_state == STATE_PLAYING:
        if not player_climbing:
            if keys[pygame.K_LEFT] or keys[pygame.K_a]: player_rect.x -= PLAYER_SPEED
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]: player_rect.x += PLAYER_SPEED
        player_rect.clamp_ip(screen.get_rect()) # Keep player on screen (horizontally for now)

        player_was_on_ladder = player_on_ladder
        player_on_ladder = False; can_climb_up = False; can_climb_down = False
        current_ladder_rect = None
        for ladder in g_level_ladders:
            if player_rect.colliderect(ladder) and abs(player_rect.centerx - ladder.centerx) < ladder.width * 0.75: # Generous horizontal check
                player_on_ladder = True; current_ladder_rect = ladder
                if player_rect.top > ladder.top: can_climb_up = True
                if player_rect.bottom < ladder.bottom + PLAYER_CLIMB_SPEED : can_climb_down = True
                break

        if player_on_ladder and current_ladder_rect:
            player_climbing_intent = False
            if (keys[pygame.K_UP] or keys[pygame.K_w]) and can_climb_up:
                player_rect.y -= PLAYER_CLIMB_SPEED; player_climbing_intent = True
            elif (keys[pygame.K_DOWN] or keys[pygame.K_s]) and can_climb_down:
                player_rect.y += PLAYER_CLIMB_SPEED; player_climbing_intent = True

            if player_climbing_intent:
                player_y_velocity = 0; player_on_ground = False; player_climbing = True
                player_rect.centerx = current_ladder_rect.centerx # Snap to ladder
            else: # No up/down key pressed while on ladder
                player_climbing = False # Not actively moving on ladder

            # Detach if moved off top/bottom of ladder while climbing
            if player_climbing and (player_rect.bottom <= current_ladder_rect.top or player_rect.top >= current_ladder_rect.bottom - PLAYER_CLIMB_SPEED):
                player_climbing = False
                # Attempt to land on a girder if at ladder top/bottom
                for g_data in g_level_girders:
                    gsy = get_girder_surface_y(player_rect, g_data)
                    if player_rect.colliderect(g_data['rect']) and abs(player_rect.bottom - gsy) < GIRDER_VISUAL_HEIGHT:
                        player_rect.bottom = gsy
                        player_on_ground = True; player_y_velocity = 0
                        break
        else:
            player_climbing = False

        if not player_climbing:
            player_y_velocity += GRAVITY
            player_rect.y += player_y_velocity

        player_on_ground_this_frame = False
        if not player_climbing:
            for girder_data in g_level_girders:
                if player_rect.right > girder_data['rect'].left and player_rect.left < girder_data['rect'].right:
                    surface_y = get_girder_surface_y(player_rect, girder_data)
                    if player_rect.bottom >= surface_y and player_rect.bottom <= surface_y + max(GIRDER_VISUAL_HEIGHT/2, abs(player_y_velocity) + 2):
                        if player_y_velocity >= -0.1 :
                            player_rect.bottom = surface_y
                            player_y_velocity = 0
                            player_on_ground_this_frame = True
                            break
            player_on_ground = player_on_ground_this_frame

        if player_rect.top > HEIGHT + player_rect.height : # Fallen completely off bottom
            player_lives -=1; player_hit_sound.play()
            if player_lives <= 0: game_state = STATE_GAME_OVER_LOST; game_over_sound.play()
            else: reset_player_position_for_level_start_or_death()

        for barrel_obj in barrels[:]:
            barrel_rect = barrel_obj['rect']
            current_girder_for_barrel = None
            if barrel_obj.get('on_girder_id'):
                for g in g_level_girders:
                    if g['id'] == barrel_obj['on_girder_id']:
                        current_girder_for_barrel = g; break

            if current_girder_for_barrel:
                barrel_rect.x += g_current_barrel_roll_speed * barrel_obj['dir']
                barrel_obj['roll_angle'] = (barrel_obj['roll_angle'] + 6 * barrel_obj['dir']) % 360
                target_y = get_girder_surface_y(barrel_rect, current_girder_for_barrel)
                barrel_rect.bottom = target_y; barrel_obj['y_vel'] = 0
                g_span_rect = current_girder_for_barrel['rect'] # Use span rect for edge check
                if not (g_span_rect.left < barrel_rect.centerx < g_span_rect.right):
                    barrel_obj['on_girder_id'] = None; barrel_obj['y_vel'] = 0.5
            else:
                barrel_obj['y_vel'] += GRAVITY * 0.6
                barrel_rect.y += barrel_obj['y_vel']
                barrel_obj['roll_angle'] = (barrel_obj['roll_angle'] + 3 * barrel_obj['dir']) % 360
                for g_check in g_level_girders:
                    if barrel_rect.colliderect(g_check['rect']): # Broad phase with visual rect
                        surface_y = get_girder_surface_y(barrel_rect, g_check)
                        if barrel_rect.bottom >= surface_y and barrel_rect.bottom <= surface_y + max(15, abs(barrel_obj['y_vel']) +2) and barrel_obj['y_vel'] >= 0:
                            barrel_rect.bottom = surface_y; barrel_obj['y_vel'] = 0
                            barrel_obj['on_girder_id'] = g_check['id']
                            if g_check['y_start'] == g_check['y_end']: pass # Keep dir or could randomize for flat
                            elif g_check['y_start'] < g_check['y_end']: barrel_obj['dir'] = 1
                            else: barrel_obj['dir'] = -1
                            break
            if barrel_rect.top > HEIGHT: barrels.remove(barrel_obj); score += 5
            if player_rect.colliderect(barrel_rect):
                player_lives -= 1; player_hit_sound.play(); barrels.remove(barrel_obj)
                if player_lives <= 0: game_state = STATE_GAME_OVER_LOST; game_over_sound.play()
                else: reset_player_position_for_level_start_or_death()
                break

        if player_rect.colliderect(g_goal_rect) and not is_level_won:
            is_level_won = True; score += (500 + (current_level_index+1)*250) # Bonus increases
            level_win_sound.play(); pygame.time.wait(1200)
            current_level_index += 1
            load_level(current_level_index) # Sets state to INTRO or VICTORY

        if game_state == STATE_PLAYING: score += (dt / 1000.0) * (current_level_index + 1) # Score rate increases with level

    # --- Drawing ---
    screen.fill(BLACK)
    for girder_data in g_level_girders:
        # Draw the girder based on its actual span and y_start/y_end for sloped ones
        # For drawing, we use y_start and y_end to define the top surface.
        # The 'rect' in girder_data is mostly for horizontal span and broad collision.
        # A simple rect for visual representation:
        pygame.draw.rect(screen, GIRDER_BROWN, girder_data['rect'])
        # To show actual slope:
        # pygame.draw.line(screen, WHITE, (girder_data['rect'].left, girder_data['y_start']), (girder_data['rect'].right, girder_data['y_end']), 1)


    for ladder_rect in g_level_ladders:
        pygame.draw.rect(screen, LADDER_CYAN, ladder_rect)
        num_rungs = max(1, int(ladder_rect.height / 15))
        for i in range(1, num_rungs + 1):
            rung_y = ladder_rect.top + (i * ladder_rect.height / (num_rungs +1) )
            pygame.draw.line(screen, BLACK, (ladder_rect.left + 2, rung_y), (ladder_rect.right - 2, rung_y), 2)

    pygame.draw.rect(screen, DK_RED, g_kong_rect)
    pygame.draw.rect(screen, PAULINE_PINK if game_state != STATE_VICTORY else TEXT_GREEN, g_goal_rect)
    pygame.draw.rect(screen, OIL_DRUM_BLUE, g_oil_drum_rect)
    pygame.draw.rect(screen, PLAYER_BLUE, player_rect)

    for barrel_obj in barrels:
        barrel_surf = pygame.Surface((BARREL_SIZE, BARREL_SIZE), pygame.SRCALPHA)
        pygame.draw.ellipse(barrel_surf, BARREL_ORANGE, (0,0,BARREL_SIZE,BARREL_SIZE))
        # Add some detail to barrel (like lines)
        pygame.draw.line(barrel_surf, BLACK, (BARREL_SIZE*0.1, BARREL_SIZE//2), (BARREL_SIZE*0.9, BARREL_SIZE//2), 2)
        pygame.draw.line(barrel_surf, BLACK, (BARREL_SIZE//2, BARREL_SIZE*0.1), (BARREL_SIZE//2, BARREL_SIZE*0.9), 2)

        rotated_barrel = pygame.transform.rotate(barrel_surf, barrel_obj['roll_angle'])
        screen.blit(rotated_barrel, rotated_barrel.get_rect(center=barrel_obj['rect'].center))


    score_surf = score_font.render(f"SCORE: {int(score)}", True, TEXT_YELLOW)
    screen.blit(score_surf, (10, 5))
    lives_surf = score_font.render(f"LIVES: {player_lives}", True, TEXT_YELLOW)
    screen.blit(lives_surf, (WIDTH - lives_surf.get_width() - 10, 5))

    if current_level_index < len(levels_data_generators) and game_state != STATE_VICTORY:
        level_name = levels_data_generators[current_level_index](WIDTH,HEIGHT)['name']
        level_name_surf = small_message_font.render(level_name, True, WHITE)
        screen.blit(level_name_surf, (WIDTH // 2 - level_name_surf.get_width()//2 , 8))

    if game_state == STATE_INTRO:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill((0,0,0,160)); screen.blit(overlay, (0,0))
        msg_text = intro_texts[intro_stage]
        msg_color = TEXT_YELLOW if intro_stage == 1 else TEXT_GREEN if intro_stage == 2 else WHITE
        msg_render = title_font.render(msg_text, True, msg_color)
        screen.blit(msg_render, (WIDTH // 2 - msg_render.get_width() // 2, HEIGHT // 2 - msg_render.get_height() //2 - 30))

    elif game_state == STATE_GAME_OVER_LOST or game_state == STATE_VICTORY:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill((0,0,0,190)); screen.blit(overlay, (0,0))
        msg_text = "GAME OVER!" if game_state == STATE_GAME_OVER_LOST else "CONGRATULATIONS!"
        msg_color = TEXT_RED if game_state == STATE_GAME_OVER_LOST else TEXT_GREEN
        msg_render = message_font.render(msg_text, True, msg_color)
        screen.blit(msg_render, (WIDTH // 2 - msg_render.get_width() // 2, HEIGHT // 2 - 60))

        if game_state == STATE_VICTORY:
            sub_msg_render = small_message_font.render("You Saved Pauline!", True, WHITE)
            screen.blit(sub_msg_render, (WIDTH // 2 - sub_msg_render.get_width() // 2, HEIGHT // 2 - 10))

        final_score_render = small_message_font.render(f"Final Score: {int(score)}", True, TEXT_YELLOW)
        screen.blit(final_score_render, (WIDTH // 2 - final_score_render.get_width() // 2, HEIGHT // 2 + 30))
        retry_render = small_message_font.render("Press 'R' to Restart", True, WHITE)
        screen.blit(retry_render, (WIDTH // 2 - retry_render.get_width() // 2, HEIGHT // 2 + 70))

    pygame.display.flip()

pygame.quit()
