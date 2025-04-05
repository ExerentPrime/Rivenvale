import aiohttp
import discord
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import requests
import json
import re
import os
from io import BytesIO
#import pytesseract
import pandas as pd
import easyocr
import torch
torch.backends.quantized.engine = 'none'

#from dotenv import load_dotenv
# Load the .env file
#load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Set up bot with intents
intents = discord.Intents.default()
client = discord.AutoShardedClient(intents=intents)
tree = app_commands.CommandTree(client)

sheet_url = "https://docs.google.com/spreadsheets/d/1zbaeJBuBn44cbVKzJins_E3hTDpnmvOk8heYN-G8yy8/export?format=xlsx"
sheet_path = r"roll_data.xlsx"
weapon_data_url = "https://content.warframe.com/PublicExport/Manifest/ExportWeapons_en.json!00_rb1u9QbKzVY3GXvQB5Nupg"
file_path = r"weapon_data.txt"
background_path = r"bg.png"
font_path = r"segoeuib.ttf"  # Segoe UI Bold font path
output_riven = r"riven_image.jpg" # Converted riven image JPG path
output_path = r"riven_grade.png" # Save grade image path
bar_buff_path = r"bar_buff.png"
bar_curse_path = r"bar_curse.png"
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # Update with your path
# pytesseract.pytesseract.tesseract_cmd = r'tesseract\tesseract.exe'  # Update with your path

# Define custom paths in YOUR project folder
custom_model_dir = os.path.join(os.getcwd(), "easyocr_models")
custom_user_dir = os.path.join(os.getcwd(), "easyocr_userdata")

def easy_ocr(output_riven):
    # Initialize EasyOCR with the custom path
    reader = easyocr.Reader(
        ['en'],
        model_storage_directory=custom_model_dir,
        user_network_directory=custom_user_dir,
        download_enabled=True,
        gpu=False
    )
    # Perform OCR
    result = reader.readtext(output_riven)

    # Extract and combine text
    extracted_text = ' '.join([detection[1] for detection in result])
    
    return extracted_text

def get_sheet_data(sheet_path, sheet_url):
    # Check if the file exists
    if not os.path.exists(sheet_path):
        print("roll_data.xlsx does not exist. Downloading...")

        # Send a GET request
        response = requests.get(sheet_url)

        # Check if request was successful
        if response.status_code == 200:
            # Save the JSON content to the file
            with open(sheet_path, "wb") as file:
                file.write(response.content)
            print(f"File saved successfully at {sheet_path}")
        else:
            print(f"Failed to download roll_data.xlsx. HTTP Status Code: {response.status_code}")
    else:
        print("roll_data.xlsx already exists. Skipping download.")

def excel_to_pandas(row, col):
    """
    Convert Excel-style references (1-based) to pandas 0-based indexing.
    
    Args:
    - row (int): The row number in Excel (1-based).
    - col (str): The column letter in Excel (e.g., 'A', 'B', 'C').

    Returns:
    - (int, int): The row and column indices in pandas (0-based).
    """
    # Convert Excel column letter to column index (0-based)
    col_index = ord(col.upper()) - ord('A')  # 'A' -> 0, 'B' -> 1, 'C' -> 2, etc.
    
    # Convert Excel row number to pandas row index (0-based)
    row_index = int(row) - 1  # Subtract 1 for 0-based indexing in pandas
    
    return row_index, col_index

# def tesseract_OCR(output_riven):
    # # Load the image using PIL (Pillow)
    # image = Image.open(output_riven)  # Replace with your image path
    # # Perform OCR on the image
    # text = pytesseract.image_to_string(image)
    
    # return text
    
def convert_image_to_jpg(image_url, output_riven):
    try:
        # Fetch the image from the given URL
        response = requests.get(image_url)
        response.raise_for_status()

        # Open the image
        image = Image.open(BytesIO(response.content))

        # Convert and save the image as JPG
        rgb_image = image.convert('RGB')  # Ensure compatibility with JPG format
        rgb_image.save(output_riven, format='JPEG')

        print(f"Image successfully converted to JPG and saved as {output_riven}")
    except Exception as e:
        print(f"Error: {e}")

async def ocr_space_file(filename):
    try:
        payload = {
            "isOverlayRequired": False,
            "apikey": "K86055554288957",
            "language": "eng",
            "ocrengine": "2",
            "scale": "true",
            "istable": "false",
        }
        with open(filename, 'rb') as f:
            r = requests.post(
                'https://api.ocr.space/parse/image',
                files={filename: f},
                data=payload,
            )

        # Decode the response and extract "ParsedText"
        response_data = json.loads(r.content.decode())
        parsed_results = response_data.get("ParsedResults", [])
        if parsed_results:
            parsed_text = parsed_results[0].get("ParsedText", "")
            return parsed_text  # Return only the parsed text
        return ""  # Return an empty string if no text is parsed

    except Exception as e:
        return f"OCRSpace process failed: {e}"  # Handle any exceptions

async def check_ocr_space_api():
    url = "https://status.ocr.space/"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    start_word = "Free OCR API"
                    end_word = "PRO API"
                    
                    if start_word in html and end_word in html:
                        start_index = html.index(start_word)
                        end_index = html.index(end_word, start_index)
                        status_text = html[start_index:end_index].strip()
                        
                        if "UP" in status_text:
                            return True, discord.Embed(title="OCR Space API Status", description="✅ UP", color=0x00FF00)
                        else:
                            return False, discord.Embed(title="OCR Space API Status", description="❌ DOWN", color=0xFF0000)
                
                return discord.Embed(title="OCR Space API Status", description="⚠️ Unable to determine status", color=0xFFA500)
        except Exception as e:
            return discord.Embed(title="OCR Space API Status", description=f"❌ Error: {str(e)}", color=0xFF0000)

def get_buff_count(extracted_text: str):
    buff_count = 0
    buff_naming = ""
    
    print(f"before get_buff_count > extracted_text : {extracted_text}")
    # Define prefixes
    prefixes = [
        "laci", "ampi", "manti", "argi", "pura", "geli", "tempi", "crita", "pleci", "acri",
        "visi", "vexi", "igni", "exi", "croni", "conci", "para", "magna", "arma", "forti",
        "sati", "toxi", "lexi", "insi", "feva", "locti", "sci", "hexa", "deci", "zeti", "hera"
    ]

    # Define suffixes
    suffixes = [
        "nus", "bin", "tron", "con", "ada", "do", "nem", "cron", "nent", "tis",
        "ata", "tio", "pha", "cta", "dra", "nak", "um", "ton", "tin", "us", "can",
        "tox", "nok", "cak", "tak", "tor", "sus", "dex", "des", "mag", "lis"
    ]

    # Combine all prefixes and suffixes to create regex patterns
    prefix_pattern = r'(?:' + '|'.join(prefixes) + r')'
    suffix_pattern = r'(?:' + '|'.join(suffixes) + r')'
    
    # Combine for regular expression:
    # 1. Match "prefix + suffix"
    # 2. Match "prefix + '-' + prefix + suffix"
    buff_naming_pattern = r'(' + prefix_pattern + r'' + suffix_pattern + r')|(' + prefix_pattern + r'-?' + prefix_pattern + r'' + suffix_pattern + r')'
    
    # Custom function to count matches based on type
    def count_matches(match):
        nonlocal buff_count, buff_naming
        # Check if it's a "prefix + suffix" match
        if match.group(1):  # The first group corresponds to prefix + suffix
            buff_count += 2
            buff_naming = match.group(1)
        # Check if it's a "prefix + '-' + prefix + suffix" match
        if match.group(2):  # The second group corresponds to prefix + '-' + prefix + suffix
            buff_count += 3
            buff_naming = match.group(2)
    
    # Use re.sub with a function to count matches and remove the patterns
    re.sub(buff_naming_pattern, count_matches, extracted_text)
    
    # Remove from extracted_text
    extracted_text = re.sub(buff_naming_pattern, '', extracted_text)
    # print(f"after get_buff_count > extracted_text : {extracted_text}")
    return buff_count, extracted_text, buff_naming

def get_weapon_data(file_path: str, weapon_data_url: str):
    # Check if the file exists
    if not os.path.exists(file_path):
        print("weapon_data.txt does not exist. Downloading...")

        # Send a GET request
        response = requests.get(weapon_data_url)

        # Check if request was successful
        if response.status_code == 200:
            # Save the JSON content to the file
            with open(file_path, "wb") as file:
                file.write(response.content)
            print(f"weapon_data.txt saved successfully at {file_path}")
        else:
            print(f"Failed to download weapon_data.txt. HTTP Status Code: {response.status_code}")
    else:
        print("weapon_data.txt already exists. Skipping download.")

def is_shotgun(weapon_name: str) -> bool:
    shotgun_weapons = [
        "Arca Plasmor", "Astilla", "Boar", "Bubonico", "Catchmoon",
        "Cedo", "Convectrix", "Corinth", "Drakgoon", "Exergis", "Felarx",
        "Hek", "Kohm", "Phage", "Phantasma", "Rauta",
        "Sobek", "Sporelacer", "Steflos", "Strun", "Sweeper",
        "Tigris", "Coda Bassocyst"
    ]
    return weapon_name in shotgun_weapons

def is_kitgun(weapon_name: str) -> bool:
    return weapon_name in {"Catchmoon", "Gaze", "Rattleguts", "Sporelacer", "Tombfinger", "Vermisplicer"}

def is_zaw(weapon_name: str) -> bool:
    if weapon_name in [
        "Balla", "Cyath", "Dehtat", "Dokrahm", "Kronsh", 
        "Mewan", "Ooltha", "Rabvee", "Sepfahn", "Plague Keewar", "Plague Kripath"
    ]:
        return True
    # elif "Plague" in weapon_name and "path" in weapon_name:  # Plague Kripath
        # return True
    else:
        return False

def get_type_sentinel_weapon(name: str) -> str:
    if name == "Akaten":
        return "Melee"
    elif name == "Artax":
        return "Rifle"
    elif name == "Batoten":
        return "Melee"
    elif name == "Burst Laser":
        return "Pistol"
    elif name == "Cryotra":
        return "Rifle"
    elif name == "Deconstructor":
        return "Melee"
    elif name == "Deth Machine Rifle":
        return "Rifle"
    elif name == "Helstrum":
        return "Rifle"
    elif name == "Lacerten":
        return "Melee"
    elif name == "Laser Rifle":
        return "Rifle"
    elif name == "Multron":
        return "Rifle"
    elif name == "Stinger":
        return "Rifle"
    elif name == "Sweeper":
        return "Shotgun"
    elif name == "Tazicor":
        return "Rifle"
    elif name == "Verglas":
        return "Rifle"
    elif name == "Vulcax":
        return "Rifle"
    elif name == "Vulklok":
        return "Rifle"
    else:
        #print("Can't find sentinel weapon type")
        return "Error"

def load_weapon_data(file_path: str):
    
    # Read file as raw text to clean invalid characters
    with open(file_path, "r", encoding="utf-8") as file:
        raw_data = file.read()
        
    # Remove control characters that might be causing JSONDecodeError
    clean_data = re.sub(r'[\x00-\x1F\x7F]', '', raw_data)
    
    # Load the JSON after cleaning
    data = json.loads(clean_data)
    
    return data

def special_case_fix(extracted_text):
    if "Twin" in extracted_text:
        return "Twin"
    elif "Dual" in extracted_text:
        if "Ether" in extracted_text:
            return "DualEther"
        else:
            return "Dual"
    elif "Mutalist" in extracted_text:
        return "Mutalist"
    elif "Proboscis" in extracted_text:
        return "Proboscis"
    else:
        return ""

def get_weapon_name(file_path: str, extracted_text: str, weapon_type: str):
    weapon_name = ""
    weapon_name_found = False
    
    data = load_weapon_data(file_path)
    
    # Dictionary to map incorrect terms to correct ones
    fixes = {
        "Ax-52": "AX-52",
        "Efv-8Mars": "EFV-8Mars",
        "Efv-5Jupiter": "EFV-5Jupiter"
    }

    # Apply replacements
    for incorrect, correct in fixes.items():
        extracted_text = extracted_text.replace(incorrect, correct)
        break

    # # Fix for AX-52
    # if "Ax-52" in extracted_text:
        # extracted_text = extracted_text.replace("Ax-52","AX-52")
    
    # # Fix for EFV-8 Mars
    # if "Efv-8Mars" in extracted_text:
        # extracted_text = extracted_text.replace("Efv-8Mars","EFV-8Mars")
    
    # # Fix for EFV-8 Jupiter
    # if "Efv-5Jupiter" in extracted_text:
        # extracted_text = extracted_text.replace("Efv-5Jupiter","EFV-5Jupiter")
    
    for weapon in data.get("ExportWeapons", []):
        temp_name = weapon['name']
        
        # Remove spaces from the name
        if " " in temp_name:
            temp_name = temp_name.replace(" ", "")
        
        # Fix dual and twin type
        special_fix = special_case_fix(extracted_text)
        if special_fix not in temp_name:
            continue
        
        # Check if the extracted_text contains the temp_name
        if temp_name in extracted_text or temp_name.title() in extracted_text:
            weapon_name = weapon['name']
            
            # Replace the temp_name and text before it in the extracted_text
            if temp_name in extracted_text:
                extracted_text = re.sub(r'.*?' + temp_name, '', extracted_text)
            elif temp_name.title() in extracted_text:
                extracted_text = re.sub(r'.*?' + temp_name.title(), '', extracted_text)
                
            weapon_name_found = True
            
            # Get weapon type
            if weapon_type == "Auto":
                temp_type = weapon['productCategory']
                if temp_type == "LongGuns":
                    if is_shotgun(weapon_name):
                        weapon_type = "Shotgun"
                    elif is_kitgun(weapon_name):
                        weapon_type = "Kitgun"
                    else:
                        weapon_type = "Rifle"
                elif temp_type == "SentinelWeapons":
                    weapon_type = get_type_sentinel_weapon(weapon_name)
                elif temp_type == "Pistols":
                    if is_zaw(weapon_name):
                        weapon_type = "Melee"
                    elif is_kitgun(weapon_name):
                        weapon_type = "Kitgun"
                    else:
                        weapon_type = "Pistol"
                elif temp_type == "Melee":
                    weapon_type = "Melee"
                elif temp_type == "SpaceGuns":
                    weapon_type = "Archgun"
            
            return weapon_name, weapon_name_found, weapon_type, extracted_text
    
    return weapon_name, weapon_name_found, weapon_type, extracted_text  # Return the values if not found

def get_weapon_dispo(file_path: str, weapon_name: str, weapon_variant: str, weapon_type: str):
    weapon_dispo = 0
    data = load_weapon_data(file_path)
    # Combine name with weapon_variant
    weapon_name = combine_with_variant(weapon_name, weapon_variant)
    
    for weapon in data.get("ExportWeapons", []):
        if weapon_name == weapon['name']:
            # Updated weapon name with variant
            weapon_name = weapon['name']
            # Get weapon disposition
            if is_kitgun(weapon_name) == True:
                if weapon_type == "Rifle" or weapon_type == "Shotgun":
                    weapon_dispo = weapon['primeOmegaAttenuation']
                elif weapon_type == "Pistol":
                    weapon_dispo = weapon['omegaAttenuation']
            else:
                weapon_dispo = weapon['omegaAttenuation']
            
            return weapon_dispo, weapon_name
    
    return weapon_dispo, weapon_name
    
def combine_with_variant(weapon_name: str, weapon_variant: str) -> str:
    if weapon_variant == "Prime":
        if "Prime" not in weapon_name:
            if "Pangolin" in weapon_name:
                return "Pangolin Prime"
            else:
                return weapon_name + " Prime"
        else:
            return weapon_name

    elif weapon_variant == "Prisma":
        if "Prisma" not in weapon_name:
            return "Prisma " + weapon_name
        else:
            return weapon_name

    elif weapon_variant == "Wraith":
        if "Wraith" not in weapon_name:
            return weapon_name + " Wraith"
        else:
            return weapon_name

    elif weapon_variant == "Tenet":
        if "Tenet" not in weapon_name:
            return "Tenet " + weapon_name
        else:
            return weapon_name

    elif weapon_variant == "Kuva":
        if "Kuva" not in weapon_name:
            return "Kuva " + weapon_name
        else:
            return weapon_name

    elif weapon_variant == "Coda":
        if "Coda" not in weapon_name:
            return "Coda " + weapon_name
        else:
            return weapon_name
            
    elif weapon_variant == "Vandal":
        if "Vandal" not in weapon_name:
            return weapon_name + " Vandal"
        else:
            return weapon_name
    
    elif weapon_variant == "Rakta":
        if "Rakta" not in weapon_name:
            return "Rakta " + weapon_name
        else:
            return weapon_name
    
    elif weapon_variant == "Telos":
        if "Telos" not in weapon_name:
            return "Telos " + weapon_name
        else:
            return weapon_name
    
    elif weapon_variant == "Vaykor":
        if "Vaykor" not in weapon_name:
            return "Vaykor " + weapon_name
        else:
            return weapon_name
    
    elif weapon_variant == "Sancti":
        if "Sancti" not in weapon_name:
            return "Sancti " + weapon_name
        else:
            return weapon_name
    
    elif weapon_variant == "Secura":
        if "Secura" not in weapon_name:
            return "Secura " + weapon_name
        else:
            return weapon_name
    
    elif weapon_variant == "Synoid":
        if "Synoid" not in weapon_name:
            return "Synoid " + weapon_name
        else:
            return weapon_name
    
    elif weapon_variant == "Dex":
        if "Dex" not in weapon_name:
            return "Dex " + weapon_name
        else:
            return weapon_name

    elif weapon_variant == "MK1":
        if "MK1" not in weapon_name:
            return "MK1-" + weapon_name
        else:
            return weapon_name

    else:
        return weapon_name

def is_riven(extracted_text: str) -> bool:
    if len(extracted_text) > 250:
        # Not a Riven mod
        return False
    else:
        # Riven mod detected
        return True

def get_value_and_stat_name(extracted_text, riven_stat_details):
    # Updated Regex pattern to match one or more numeric values followed by text
    pattern = r"(\+?\d+(\.\d+)?[a-zA-Z%]+)"

    # Use re.findall to capture all matches
    matches = re.findall(pattern, extracted_text)
    print(f"get_value_and_stat_name Input Text: {extracted_text}")
    
    # Ensure we have at least 2 and at most 4 matches
    if len(matches) < 2:
        print("Error: Less than 2 valid stats found!")
        riven_stat_details.StatName = [""] * 4  # Reset StatName array
        print(riven_stat_details.StatName)
        return  # Early exit for invalid input
    
    # Extract up to 4 stats
    for i in range(min(len(matches), 4)):
        match = matches[i][0]  # Full match
        
        # Split numeric value and stat name using a custom approach
        numeric_value = re.search(r"(\+?\d+(\.\d+)?)", match).group(1)
        temp_name = match[len(numeric_value):]  # The remainder is the stat name
        
        if get_stat_name(temp_name) != "can't find stat name": 
            stat_name = get_stat_name(temp_name)
        
            # Safely store the results in riven_stat_details
            riven_stat_details.Value[i] = float(numeric_value) if numeric_value else 0.0
            riven_stat_details.StatName[i] = stat_name if stat_name else ""
        
        # Print the extracted stats to the console
        # print(f"Stat {i+1}: {riven_stat_details.Value[i]} {riven_stat_details.StatName[i]}")

    # Handle any remaining slots if fewer than 4 matches
    # for i in range(len(matches), 4):
        # riven_stat_details.Value[i] = 0.0
        # riven_stat_details.StatName[i] = ""
        # print(f"Stat {i+1}: {riven_stat_details.Value[i]} {riven_stat_details.StatName[i]}")

    # Final logging
    # print(riven_stat_details.StatName)

def get_stat_name(input_string):
    if "additional" in input_string:
        return "Additional Combo Count Chance"
    elif "ammo" in input_string:
        return "Ammo Maximum"
    elif "corpus" in input_string:
        return "Damage to Corpus"
    elif "grineer" in input_string:
        return "Damage to Grineer"
    elif "infested" in input_string:
        return "Damage to Infested"
    elif "cold" in input_string:
        return "Cold"
    elif "comboduration" in input_string:
        return "Combo Duration"
    elif "criticalchancefor" in input_string:
        return "Critical Chance for Slide Attack"
    elif "criticalchance" in input_string:
        return "Critical Chance"
    elif "criticaldamage" in input_string:
        return "Critical Damage"
    elif "meleedamage" in input_string:
        return "Melee Damage"
    elif "electricity" in input_string:
        return "Electricity"
    elif "heat" in input_string:
        return "Heat"
    elif "finisherdamage" in input_string:
        return "Finisher Damage"
    elif "damage" in input_string:
        return "Damage"
    elif "firerate" in input_string:
        return "Fire Rate"
    elif "attackspeed" in input_string:
        return "Attack Speed"
    elif "projectile" in input_string:
        return "Projectile Speed"
    elif "initialcombo" in input_string:
        return "Initial Combo"
    elif "impact" in input_string:
        return "Impact"
    elif "magazine" in input_string:
        return "Magazine Capacity"
    elif "heavyattack" in input_string:
        return "Heavy Attack Efficiency"
    elif "multishot" in input_string:
        return "Multishot"
    elif "toxin" in input_string:
        return "Toxin"
    elif "punchthrough" in input_string:
        return "Punch Through"
    elif "puncture" in input_string:
        return "Puncture"
    elif "reloadspeed" in input_string:
        return "Reload Speed"
    elif "range" in input_string:
        return "Range"
    elif "slash" in input_string:
        return "Slash"
    elif "statuschance" in input_string:
        return "Status Chance"
    elif "statusduration" in input_string:
        return "Status Duration"
    elif "weaponreco" in input_string:
        return "Weapon Recoil"
    elif "zoom" in input_string:
        return "Zoom"
    else:
        return "can't find stat name"

def get_stat_count(riven_stat_details):
    count = 0
    for i in range(4):  # Loop from 0 to 3 (inclusive)
        if riven_stat_details.StatName[i] != "":
            count += 1
    return count

def get_riven_type(riven_stat_details):
    if riven_stat_details.BuffCount == 2 and riven_stat_details.CurseCount == 0:
        riven_stat_details.RivenType = "2 Buff 0 Curse"
    elif riven_stat_details.BuffCount == 2 and riven_stat_details.CurseCount == 1:
        riven_stat_details.RivenType = "2 Buff 1 Curse"
    elif riven_stat_details.BuffCount == 3 and riven_stat_details.CurseCount == 0:
        riven_stat_details.RivenType = "3 Buff 0 Curse"
    elif riven_stat_details.BuffCount == 3 and riven_stat_details.CurseCount == 1:
        riven_stat_details.RivenType = "3 Buff 1 Curse"
    else:
        riven_stat_details.RivenType = "Unknown Riven Type"

def calculate_max(base_stat: float, weapon_dispo: float, riven_value: float) -> float:
    max_value = 1.1 * base_stat * weapon_dispo * riven_value
    return abs(max_value)  # Ensure the value is always positive

def calculate_min(base_stat: float, weapon_dispo: float, riven_value: float) -> float:
    min_value = 0.9 * base_stat * weapon_dispo * riven_value
    return abs(min_value)  # Ensure the value is always positive

def get_base_stat(stat: str, weapon_type: str) -> float:
    if stat == "Additional Combo Count Chance":
        return 58.77
    elif stat == "Chance to Gain Combo Count":
        return 104.85
    elif stat == "Ammo Maximum":
        if weapon_type == "Rifle":
            return 49.95
        elif weapon_type in ["Shotgun", "Pistol"]:
            return 90
        else:
            return 99.9  # Archgun
    elif stat in ["Damage to Corpus", "Damage to Grineer", "Damage to Infested"]:
        return 45
    elif stat in ["Cold", "Electricity", "Heat", "Toxin"]:
        if weapon_type == "Archgun":
            return 119.7
        else:
            return 90
    elif stat == "Combo Duration":
        return 8.1
    elif stat == "Critical Chance":
        if weapon_type in ["Rifle", "Pistol"]:
            return 149.99
        elif weapon_type == "Shotgun":
            return 90
        elif weapon_type == "Archgun":
            return 99.9
        else:
            return 180  # Melee
    elif stat == "Critical Chance for Slide Attack":
        return 120
    elif stat == "Critical Damage":
        if weapon_type == "Rifle":
            return 120
        elif weapon_type in ["Shotgun", "Pistol", "Melee"]:
            return 90
        else:
            return 80.1  # Archgun
    elif stat in ["Damage", "Melee Damage"]:
        if weapon_type == "Rifle":
            return 165
        elif weapon_type in ["Shotgun", "Melee"]:
            return 164.7
        elif weapon_type == "Pistol":
            return 219.6
        else:
            return 99.9  # Archgun
    elif stat == "Finisher Damage":
        return 119.7
    elif stat in ["Fire Rate", "Attack Speed"]:
        if weapon_type in ["Rifle", "Archgun"]:
            return 60.03
        elif weapon_type == "Shotgun":
            return 89.1
        elif weapon_type == "Pistol":
            return 74.7
        else:
            return 54.9  # Melee
    elif stat == "Projectile Speed":
        if weapon_type in ["Rifle", "Pistol"]:
            return 90
        else:
            return 89.1  # Shotgun
    elif stat == "Initial Combo":
        return 24.5
    elif stat in ["Impact", "Puncture", "Slash"]:
        if weapon_type == "Archgun":
            return 90
        else:
            return 119.97
    elif stat == "Magazine Capacity":
        if weapon_type == "Archgun":
            return 60.3
        else:
            return 50
    elif stat == "Heavy Attack Efficiency":
        return 73.44
    elif stat == "Multishot":
        if weapon_type == "Rifle":
            return 90
        elif weapon_type in ["Shotgun", "Pistol"]:
            return 119.7
        else:
            return 60.3  # Archgun
    elif stat == "Punch Through":
        return 2.7
    elif stat == "Reload Speed":
        if weapon_type in ["Rifle", "Pistol"]:
            return 50
        elif weapon_type == "Shotgun":
            return 49.45
        else:
            return 99.9
    elif stat == "Range":
        return 1.94
    elif stat == "Status Chance":
        if weapon_type == "Archgun":
            return 60.3
        else:
            return 90
    elif stat == "Status Duration":
        if weapon_type in ["Rifle", "Pistol", "Archgun"]:
            return 99.99
        else:
            return 99
    elif stat == "Weapon Recoil":
        return 90
    elif stat == "Zoom":
        if weapon_type in ["Rifle", "Archgun"]:
            return 59.99
        else:
            return 80.1
    else:
        print(f" Can't find this stat : {stat}")
        # raise ValueError(f"Base stat ERROR or not exist: {stat}")

def calculate_stats(riven_stat_details, weapon_type, weapon_dispo):
    if riven_stat_details.RivenType == "2 Buff 0 Curse":
        for i in range(riven_stat_details.StatCount):
            base_stat = get_base_stat(riven_stat_details.StatName[i], weapon_type)
            riven_stat_details.Min[i] = calculate_min(base_stat, weapon_dispo, 0.99)
            riven_stat_details.Max[i] = calculate_max(base_stat, weapon_dispo, 0.99)

    elif riven_stat_details.RivenType == "2 Buff 1 Curse":
        for i in range(2):
            base_stat = get_base_stat(riven_stat_details.StatName[i], weapon_type)
            riven_stat_details.Min[i] = calculate_min(base_stat, weapon_dispo, 1.2375)
            riven_stat_details.Max[i] = calculate_max(base_stat, weapon_dispo, 1.2375)

        base_stat = get_base_stat(riven_stat_details.StatName[2], weapon_type)
        riven_stat_details.Min[2] = calculate_min(base_stat, weapon_dispo, -0.495)
        riven_stat_details.Max[2] = calculate_max(base_stat, weapon_dispo, -0.495)
        # if "Recoil" in riven_stat_details.StatName[2]:
            # riven_stat_details.Min[2] *= -1
            # riven_stat_details.Max[2] *= -1

    elif riven_stat_details.RivenType == "3 Buff 0 Curse":
        for i in range(3):
            base_stat = get_base_stat(riven_stat_details.StatName[i], weapon_type)
            riven_stat_details.Min[i] = calculate_min(base_stat, weapon_dispo, 0.75)
            riven_stat_details.Max[i] = calculate_max(base_stat, weapon_dispo, 0.75)

    elif riven_stat_details.RivenType == "3 Buff 1 Curse":
        for i in range(3):
            base_stat = get_base_stat(riven_stat_details.StatName[i], weapon_type)
            riven_stat_details.Min[i] = calculate_min(base_stat, weapon_dispo, 0.9375)
            riven_stat_details.Max[i] = calculate_max(base_stat, weapon_dispo, 0.9375)

        base_stat = get_base_stat(riven_stat_details.StatName[3], weapon_type)
        riven_stat_details.Min[3] = calculate_min(base_stat, weapon_dispo, -0.75)
        riven_stat_details.Max[3] = calculate_max(base_stat, weapon_dispo, -0.75)
        # if "Recoil" in riven_stat_details.StatName[3]:
            # riven_stat_details.Min[3] *= -1
            # riven_stat_details.Max[3] *= -1

def get_prefix_and_unit(riven_stat_details):
    # PREFIX
    if riven_stat_details.RivenType == "2 Buff 0 Curse":
        for i in range(2):  # Loops through indices 0 and 1
            if "Weapon Recoil" in riven_stat_details.StatName[i]:
                riven_stat_details.Prefix[i] = "-"
            elif "Damage to" in riven_stat_details.StatName[i]:
                riven_stat_details.Prefix[i] = "x"
            else:
                riven_stat_details.Prefix[i] = "+"
    elif riven_stat_details.RivenType == "2 Buff 1 Curse":
        for i in range(2):
            if "Weapon Recoil" in riven_stat_details.StatName[i]:
                riven_stat_details.Prefix[i] = "-"
            elif "Damage to" in riven_stat_details.StatName[i]:
                riven_stat_details.Prefix[i] = "x"
            else:
                riven_stat_details.Prefix[i] = "+"
        # Handling the 3rd stat
        if "Weapon Recoil" in riven_stat_details.StatName[2]:
            riven_stat_details.Prefix[2] = "+"
        elif "Damage to" in riven_stat_details.StatName[2]:
                riven_stat_details.Prefix[2] = "x"
        else:
            riven_stat_details.Prefix[2] = "-"
    elif riven_stat_details.RivenType == "3 Buff 0 Curse":
        for i in range(3):  # Loops through indices 0, 1, and 2
            if "Weapon Recoil" in riven_stat_details.StatName[i]:
                riven_stat_details.Prefix[i] = "-"
            elif "Damage to" in riven_stat_details.StatName[i]:
                riven_stat_details.Prefix[i] = "x"
            else:
                riven_stat_details.Prefix[i] = "+"
    elif riven_stat_details.RivenType == "3 Buff 1 Curse":
        for i in range(3):
            if "Weapon Recoil" in riven_stat_details.StatName[i]:
                riven_stat_details.Prefix[i] = "-"
            elif "Damage to" in riven_stat_details.StatName[i]:
                riven_stat_details.Prefix[i] = "x"
            else:
                riven_stat_details.Prefix[i] = "+"
        # Handling the 4th stat
        if "Weapon Recoil" in riven_stat_details.StatName[3]:
            riven_stat_details.Prefix[3] = "+"
        elif "Damage to" in riven_stat_details.StatName[3]:
                riven_stat_details.Prefix[3] = "x"
        else:
            riven_stat_details.Prefix[3] = "-"

    # UNIT
    for i in range(riven_stat_details.StatCount):
        riven_stat_details.Unit[i] = get_unit(riven_stat_details.StatName[i])

def get_unit(stat_name):
    if stat_name == "Combo Duration":
        return "s"
    elif stat_name in ["Range", "Punch Through", "Initial Combo", "Damage to Grineer", "Damage to Corpus", "Damage to Infested"]:
        return ""
    else:
        return "%"

def percentage_to_decimal(riven_stat_details, i):
    if "Damage to" in riven_stat_details.StatName[i]:
        if i == riven_stat_details.StatCount - 1 and i != 1 and "1" in riven_stat_details.RivenType:
            riven_stat_details.Value[i] = round((100 - riven_stat_details.Value[i]) / 100, 2)
            riven_stat_details.Min[i] = round((100 - riven_stat_details.Min[i]) / 100, 2)
            riven_stat_details.Max[i] = round((100 - riven_stat_details.Max[i]) / 100, 2)
        else:
            riven_stat_details.Value[i] = round(riven_stat_details.Value[i] / 100 + 1, 2)
            riven_stat_details.Min[i] = round(riven_stat_details.Min[i] / 100 + 1, 2)
            riven_stat_details.Max[i] = round(riven_stat_details.Max[i] / 100 + 1, 2)
            
def damage_to_faction_fix(riven_stat_details, i):
    if "Damage to" in riven_stat_details.StatName[i]:
        if riven_stat_details.Value[i] >= 1:
            riven_stat_details.Value[i] = riven_stat_details.Value[i] * 100 - 100
        else:
            riven_stat_details.Value[i] = (1 - riven_stat_details.Value[i]) * 100

def get_grade(grade_value, grade_type):
    if grade_type != "Curse":
        if grade_value <= -9.5:
            return "F"
        elif grade_value > -9.5 and grade_value <= -7.5:
            return "C-"
        elif grade_value > -7.5 and grade_value <= -5.5:
            return "C"
        elif grade_value > -5.5 and grade_value <= -3.5:
            return "C+"
        elif grade_value > -3.5 and grade_value <= -1.5:
            return "B-"
        elif grade_value > -1.5 and grade_value <= 1.5:
            return "B"
        elif grade_value > 1.5 and grade_value <= 3.5:
            return "B+"
        elif grade_value > 3.5 and grade_value <= 5.5:
            return "A-"
        elif grade_value > 5.5 and grade_value <= 7.5:
            return "A"
        elif grade_value > 7.5 and grade_value <= 9.5:
            return "A+"
        elif grade_value > 9.5:
            return "S"
        else:
            # print("GRADING ERROR. Make sure weapon variant selected is correct")
            return "ERR"
    else:
        if grade_value <= -9.5:
            return "S"
        elif grade_value > -9.5 and grade_value <= -7.5:
            return "A+"
        elif grade_value > -7.5 and grade_value <= -5.5:
            return "A"
        elif grade_value > -5.5 and grade_value <= -3.5:
            return "A-"
        elif grade_value > -3.5 and grade_value <= -1.5:
            return "B+"
        elif grade_value > -1.5 and grade_value <= 1.5:
            return "B"
        elif grade_value > 1.5 and grade_value <= 3.5:
            return "B-"
        elif grade_value > 3.5 and grade_value <= 5.5:
            return "C+"
        elif grade_value > 5.5 and grade_value <= 7.5:
            return "C"
        elif grade_value > 7.5 and grade_value <= 9.5:
            return "C-"
        elif grade_value > 9.5:
            return "F"
        else:
            # print("GRADING ERROR. Make sure weapon variant selected is correct")
            return "ERR"

def set_grade(riven_stat_details, weapon_type, weapon_dispo, riven_rank):
    if riven_stat_details.RivenType == "2 Buff 0 Curse":
        for i in range(2):
            if riven_rank == "Unranked":
                temp_value = riven_stat_details.Value[i] * 9
            else:
                temp_value = riven_stat_details.Value[i]
            grade_value = get_base_stat(riven_stat_details.StatName[i], weapon_type) * 0.99 * weapon_dispo
            grade_value = (temp_value / grade_value) * 100 - 100
            grade_value = round(grade_value, 3)
            print(f"Grade Value Buff {i+1} : {grade_value}")
            riven_stat_details.Grade[i] = get_grade(grade_value, "Buff")

    elif riven_stat_details.RivenType == "2 Buff 1 Curse":
        for i in range(2):
            if riven_rank == "Unranked":
                temp_value = riven_stat_details.Value[i] * 9
            else:
                temp_value = riven_stat_details.Value[i]
            grade_value = get_base_stat(riven_stat_details.StatName[i], weapon_type) * 1.2375 * weapon_dispo
            grade_value = (temp_value / grade_value) * 100 - 100
            grade_value = round(grade_value, 3)
            print(f"Grade Value Buff {i+1} : {grade_value}")
            riven_stat_details.Grade[i] = get_grade(grade_value, "Buff")
        
        if riven_rank == "Unranked":
            temp_value = riven_stat_details.Value[2] * 9
        else:
            temp_value = riven_stat_details.Value[2]
        grade_value = get_base_stat(riven_stat_details.StatName[2], weapon_type) * 0.495 * weapon_dispo
        grade_value = (temp_value / grade_value) * 100 - 100
        grade_value = round(grade_value, 3)
        print(f"Grade Value Stat Curse : {grade_value}")
        riven_stat_details.Grade[2] = get_grade(grade_value, "Curse")
         
    elif riven_stat_details.RivenType == "3 Buff 0 Curse":
        for i in range(3):
            if riven_rank == "Unranked":
                temp_value = riven_stat_details.Value[i] * 9
            else:
                temp_value = riven_stat_details.Value[i]
            grade_value = get_base_stat(riven_stat_details.StatName[i], weapon_type) * 0.75 * weapon_dispo
            grade_value = (temp_value / grade_value) * 100 - 100
            grade_value = round(grade_value, 3)
            print(f"Grade Value Buff {i+1} : {grade_value}")
            riven_stat_details.Grade[i] = get_grade(grade_value, "Buff")
            
    else: # 3 Buff 1 Curse
        for i in range(3):
            if riven_rank == "Unranked":
                temp_value = riven_stat_details.Value[i] * 9
            else:
                temp_value = riven_stat_details.Value[i]
            
            # normalize = (riven_stat_details.Value[i] - riven_stat_details.Min[i]) / (riven_stat_details.Max[i] - riven_stat_details.Min[i])
            # grade_value = -0.10 + (normalize*(0.10-(-0.10)))
            # grade_value *= 100
            grade_value = get_base_stat(riven_stat_details.StatName[i], weapon_type) * 0.9375 * weapon_dispo
            grade_value = (temp_value / grade_value) * 100 - 100
            grade_value = round(grade_value, 3)
            print(f"Grade Value Buff {i+1} : {grade_value}")
            riven_stat_details.Grade[i] = get_grade(grade_value, "Buff")
        
        if riven_rank == "Unranked":
            temp_value = riven_stat_details.Value[3] * 9
        else:
            temp_value = riven_stat_details.Value[3]
        # normalize = (riven_stat_details.Value[3] - riven_stat_details.Min[3]) / (riven_stat_details.Max[3] - riven_stat_details.Min[3])
        # grade_value = -0.10 + (normalize*(0.10-(-0.10)))
        # grade_value *= 100
        grade_value = get_base_stat(riven_stat_details.StatName[3], weapon_type) * 0.75 * weapon_dispo
        grade_value = (temp_value / grade_value) * 100 - 100
        grade_value = round(grade_value, 3)
        print(f"Grade Value Curse : {grade_value}")
        riven_stat_details.Grade[3] = get_grade(grade_value, "Curse")

# Define a function that returns a color based on the grade
def get_grade_color(grade):
    grade_colors = {
        "S": "#28fe00",
        "A+": "#88e500",
        "A": "#88e500",
        "A-": "#a7d200",
        "B+": "#bfbd01",
        "B": "#d3a601",
        "B-": "#e18f00",
        "C+": "#ed7400",
        "C": "#f65901",
        "C-": "#fc3800",
        "F": "#ff0200"
    }
    
    return grade_colors.get(grade, "White")

def create_grading_image(riven_stat_details, weapon_name, weapon_dispo, image_url, platinum):
    # Set file paths
    global background_path
    global font_path

    # Load the background image
    background = Image.open(background_path)

    # Load the left image
    response = requests.get(image_url)
    if response.status_code == 200:
        riven_image = Image.open(BytesIO(response.content))  # Open the image from the URL
        # Define the dimensions of the box area
        box_width, box_height = 240, 350
        # Resize the image to fit within the box area while maintaining aspect ratio
        riven_image.thumbnail((box_width, box_height))
        
        riven_image_x = 33 + (box_width - riven_image.width) // 2
        riven_image_y = (box_height - riven_image.height) // 2
        background.paste(riven_image, (riven_image_x, riven_image_y))

    # Draw on the background
    draw = ImageDraw.Draw(background)

    # Define the fonts
    font_size = 12
    grade_font_size = 24
    platinum_font_size = 36
    dpi = 96
    scaling_factor = dpi / 72
    adjusted_grade_font_size = int(grade_font_size * scaling_factor)
    adjusted_statname_font_size = int(font_size * scaling_factor)
    adjusted_platinum_font_size = int(platinum_font_size * scaling_factor)

    grade_font = ImageFont.truetype(font_path, adjusted_grade_font_size)
    default_font = ImageFont.truetype(font_path, adjusted_statname_font_size)
    platinum_font = ImageFont.truetype(font_path, adjusted_platinum_font_size)
    
    if platinum != None:
        # Draw platinum background
        platinum = platinum[:6]
        platinum_bg = Image.open("plat_bg.png").convert("RGBA")
        background.paste(platinum_bg, (34, 285), platinum_bg)
    
        # Draw platinum value
        platinum_text = str(platinum)
        platinum_textbox = (64, 295, 245, 331)
        text_bbox = draw.textbbox((0, 0), platinum_text, font=platinum_font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        textbox_width = platinum_textbox[2] - platinum_textbox[0]
        textbox_height = platinum_textbox[3] - platinum_textbox[1]
        x_position = platinum_textbox[0] + (textbox_width - text_width) // 2
        #y_position = platinum_textbox[1] + (textbox_height - text_height) // 2
        draw.text((x_position, 280), platinum_text, fill="#826aa6", font=platinum_font)
    
    # Draw weapon name
    weapon_name = weapon_name.upper()
    weapon_textbox = (354, 20, 655, 40)
    text_bbox = draw.textbbox((0, 0), weapon_name, font=default_font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    textbox_width = weapon_textbox[2] - weapon_textbox[0]
    textbox_height = weapon_textbox[3] - weapon_textbox[1]
    x_position = weapon_textbox[0] + (textbox_width - text_width) // 2
    # y_position = weapon_textbox[1] + (textbox_height - text_height) // 2
    draw.text((x_position, 20), weapon_name, fill="white", font=default_font)
    
    # Draw weapon disposition
    weapon_dispo = f"Disposition {weapon_dispo:.2f}"
    dispo_textbox = (350, 300, 655, 320)
    text_bbox = draw.textbbox((0, 0), weapon_dispo, font=default_font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    textbox_width = dispo_textbox[2] - dispo_textbox[0]
    textbox_height = dispo_textbox[3] - dispo_textbox[1]
    x_position = dispo_textbox[0] + (textbox_width - text_width) // 2
    # y_position = dispo_textbox[1] + (textbox_height - text_height) // 2
    draw.text((x_position, 315), weapon_dispo, fill="white", font=default_font)

    # Draw grades
    grades = [
        {"grade": riven_stat_details.Grade[0], "position": (293, 45)},
        {"grade": riven_stat_details.Grade[1], "position": (293, 113)},
        {"grade": riven_stat_details.Grade[2], "position": (293, 181)},
        {"grade": riven_stat_details.Grade[3], "position": (293, 249)},
    ]

    for grade_data in grades:
        grade_text = grade_data["grade"]
        position = grade_data["position"]
        if grade_text != "":
            fill_color = get_grade_color(grade_text)
            draw.text(position, grade_text, fill=fill_color, font=grade_font)

    # Draw stat names
    # Round to 1 decimal place
    # for i in range(riven_stat_details.StatCount):
        # if "Damage to" in riven_stat_details.StatName[i]:
            # riven_stat_details.Value[i] = round(riven_stat_details.Value[i], 1)
        
    combine_stat_1 = str(riven_stat_details.Prefix[0]) + str(riven_stat_details.Value[0]) + str(riven_stat_details.Unit[0] + " " + str(riven_stat_details.StatName[0]))
    combine_stat_2 = str(riven_stat_details.Prefix[1]) + str(riven_stat_details.Value[1]) + str(riven_stat_details.Unit[1] + " " + str(riven_stat_details.StatName[1]))
    combine_stat_3 = str(riven_stat_details.Prefix[2]) + str(riven_stat_details.Value[2]) + str(riven_stat_details.Unit[2] + " " + str(riven_stat_details.StatName[2]))
    combine_stat_4 = str(riven_stat_details.Prefix[3]) + str(riven_stat_details.Value[3]) + str(riven_stat_details.Unit[3] + " " + str(riven_stat_details.StatName[3]))
    
    statnames = [
        {"statname": combine_stat_1, "position": (354, 45)},
        {"statname": combine_stat_2, "position": (354, 113)},
        {"statname": combine_stat_3, "position": (354, 181)},
        {"statname": combine_stat_4, "position": (354, 249)},
    ]
    for statname_data in statnames:
        statname_text = statname_data["statname"]
        position = statname_data["position"]
        if "999.9" not in statname_text:
            draw.text(position, statname_text, fill="white", font=default_font)

    # Draw min stats
    # Round to 1 decimal place
    for i in range(riven_stat_details.StatCount):
        if not "Damage to" in riven_stat_details.StatName[i]:
            riven_stat_details.Min[i] = round(riven_stat_details.Min[i], 1)
    
    combine_stat_1 = "MIN " + str(riven_stat_details.Prefix[0]) + str(riven_stat_details.Min[0]) + str(riven_stat_details.Unit[0])
    combine_stat_2 = "MIN " + str(riven_stat_details.Prefix[1]) + str(riven_stat_details.Min[1]) + str(riven_stat_details.Unit[1])
    combine_stat_3 = "MIN " + str(riven_stat_details.Prefix[2]) + str(riven_stat_details.Min[2]) + str(riven_stat_details.Unit[2])
    combine_stat_4 = "MIN " + str(riven_stat_details.Prefix[3]) + str(riven_stat_details.Min[3]) + str(riven_stat_details.Unit[3])
    
    min_stats = [
        {"min": combine_stat_1, "position": (354, 65)},
        {"min": combine_stat_2, "position": (354, 133)},
        {"min": combine_stat_3, "position": (354, 201)},
        {"min": combine_stat_4, "position": (354, 269)},
    ]
    for min_data in min_stats:
        min_text = min_data["min"]
        position = min_data["position"]
        if "999.9" not in min_text:
            draw.text(position, min_text, fill="white", font=default_font)

    # Draw max stats
    # Round to 1 decimal place
    for i in range(riven_stat_details.StatCount):
        if not "Damage to" in riven_stat_details.StatName[i]:
            riven_stat_details.Max[i] = round(riven_stat_details.Max[i], 1)
        
    combine_stat_1 = "MAX " + str(riven_stat_details.Prefix[0]) + str(riven_stat_details.Max[0]) + str(riven_stat_details.Unit[0])
    combine_stat_2 = "MAX " + str(riven_stat_details.Prefix[1]) + str(riven_stat_details.Max[1]) + str(riven_stat_details.Unit[1])
    combine_stat_3 = "MAX " + str(riven_stat_details.Prefix[2]) + str(riven_stat_details.Max[2]) + str(riven_stat_details.Unit[2])
    combine_stat_4 = "MAX " + str(riven_stat_details.Prefix[3]) + str(riven_stat_details.Max[3]) + str(riven_stat_details.Unit[3])
    
    max_stats = [
        {"max": combine_stat_1, "position": (520, 65)},
        {"max": combine_stat_2, "position": (520, 133)},
        {"max": combine_stat_3, "position": (520, 201)},
        {"max": combine_stat_4, "position": (520, 269)},
    ]
    for max_data in max_stats:
        max_text = max_data["max"]
        y_position = max_data["position"][1]
        right_boundary = 655
        text_bbox = draw.textbbox((0, 0), max_text, font=default_font)
        text_width = text_bbox[2] - text_bbox[0]
        x_position = right_boundary - text_width
        if "999.9" not in max_text:
            draw.text((x_position, y_position), max_text, fill="white", font=default_font)
    
    # Draw bar chart
    global bar_buff
    global bar_curse
    bar_buff = bar_buff_path
    bar_curse = bar_curse_path
    bar_x = 354
    bar_y = 90

    for i in range(riven_stat_details.StatCount):
        # Convert back to percentage
        if "Damage to" in riven_stat_details.StatName[i]:
            if riven_stat_details.Value[i] >= 1:
                riven_stat_details.Value[i] = riven_stat_details.Value[i] * 100 - 100
                riven_stat_details.Min[i] = riven_stat_details.Min[i] * 100 - 100
                riven_stat_details.Max[i] = riven_stat_details.Max[i] * 100 - 100
            else:
                riven_stat_details.Value[i] = (1 - riven_stat_details.Value[i]) * 100
                riven_stat_details.Min[i] = (1 - riven_stat_details.Min[i]) * 100
                riven_stat_details.Max[i] = (1 - riven_stat_details.Max[i]) * 100
                
        # Define the dimensions of the box area
        box_width, box_height = 301, 13
        percent = bar_resize(riven_stat_details.Min[i], riven_stat_details.Max[i], riven_stat_details.Value[i]) * 301
        box_width = int(percent)
        if box_width == 0:
            box_width = 1
        
        if i == riven_stat_details.StatCount - 1 and i != 1 and "1" in riven_stat_details.RivenType:
            bar = Image.open(bar_curse)
        else:
            bar = Image.open(bar_buff)
    
        # Define the target size
        target_size = (box_width, box_height)
        
        # Resize the image without keeping the aspect ratio
        stretched_bar = bar.resize(target_size, Image.Resampling.LANCZOS)
        
        # Paste the resized image into the background at the specified position
        background.paste(stretched_bar, (bar_x, bar_y))
        
        # Update bar_y for spacing
        bar_y = bar_y + 68  # Spacing for bar

        
    # Save the resulting image
    global output_path
    # Convert the image to RGB (removing the alpha channel)
    background = background.convert("RGB")
    background.save(output_path, format="JPEG", dpi=(dpi, dpi))
    print(f"Image saved at {output_path} with {dpi} DPI!")

def bar_resize(min_value: float, max_value: float, value: float) -> float:
    if value > max_value:
        return 1
    elif value < min_value:
        return 0
    else:
        diff = max_value - min_value
        temp = value - min_value
        percent = temp / diff
        return percent


def check_out_range(riven_stat_details):
    out_range = False
    out_range_faction = False
    
    for i in range(riven_stat_details.StatCount):
        if riven_stat_details.Value[i] < riven_stat_details.Min[i] or riven_stat_details.Value[i] > riven_stat_details.Max[i]:
            if "Damage to" in riven_stat_details.StatName[i]:
                out_range_faction = True
            else:
                out_range = True
    
    return out_range, out_range_faction
    
class RivenStatDetails:
    def __init__(self):
        self.Prefix = [""] * 4  # List of 4 characters (equivalent to Char array)
        self.Value = [999.9] * 4   # List of 4 doubles (floating-point numbers)
        self.StatName = [""] * 4  # List of 4 strings
        self.Unit = [""] * 4  # List of 4 strings
        self.BuffCount = 0      # Integer
        self.CurseCount = 0     # Integer
        self.StatCount = 0      # Integer
        self.RivenType = ""   # String
        self.Min = [999.9] * 4   # List of 4 doubles (floating-point numbers)
        self.Max = [999.9] * 4   # List of 4 doubles (floating-point numbers)
        self.Grade = [""] * 4

@tree.command(name="legend", description="Legend/Key")
async def status(interaction: discord.Interaction):
    embed_content = """
AS    : Attack Speed
CC    : Critical Chance
CD    : Critical Damage
DTC   : Damage to Corpus
DTG   : Damage to Grineer
DTI   : Damage to Infested
DMG   : Damage
EFF   : Heavy Attack Efficiency
ELEC  : Electricity
FIN   : Finisher Damage
FR    : Fire Rate
IC    : Initial Combo
IMP   : Impact
MAG   : Magazine Capacity
MS    : Multishot
PFS   : Projectile Flight Speed
PT    : Punch Through
PUNC  : Puncture
REC   : Recoil
RLS   : Reload Speed
SC    : Status Chance
SD    : Status Duration
SLIDE : Critical Hit on Slide
TOX   : Toxin
"""
    await interaction.response.send_message(f"```{embed_content}```")

@tree.command(name="status", description="OCRSpace API status.")
async def status(interaction: discord.Interaction):
    _, embed = await check_ocr_space_api()  # Unpack the tuple
    await interaction.response.send_message(embed=embed)

@tree.command(name="grading", description="Grading a Riven mod.")
@app_commands.choices(
    weapon_variant=[
        app_commands.Choice(name="Normal", value="Normal"),
        app_commands.Choice(name="Prime", value="Prime"),
        app_commands.Choice(name="Prisma", value="Prisma"),
        app_commands.Choice(name="Wraith", value="Wraith"),
        app_commands.Choice(name="Tenet", value="Tenet"),
        app_commands.Choice(name="Kuva", value="Kuva"),
        app_commands.Choice(name="Coda", value="Coda"),
        app_commands.Choice(name="Vandal", value="Vandal"),
        app_commands.Choice(name="Rakta", value="Rakta"),
        app_commands.Choice(name="Telos", value="Telos"),
        app_commands.Choice(name="Vaykor", value="Vaykor"),
        app_commands.Choice(name="Sancti", value="Sancti"),
        app_commands.Choice(name="Secura", value="Secura"),
        app_commands.Choice(name="Synoid", value="Synoid"),
        app_commands.Choice(name="Dex", value="Dex"),
        app_commands.Choice(name="MK1", value="MK1"),
    ],
    
    weapon_type=[
        app_commands.Choice(name="Auto Detect (except Kitguns)", value="Auto"),
        app_commands.Choice(name="Rifle", value="Rifle"),
        app_commands.Choice(name="Shotgun", value="Shotgun"),
        app_commands.Choice(name="Pistol", value="Pistol"),
        app_commands.Choice(name="Melee", value="Melee"),
        app_commands.Choice(name="Archgun", value="Archgun"),
    ],
    
    riven_rank=[
        app_commands.Choice(name="Maxed", value="Maxed"),
        app_commands.Choice(name="Unranked", value="Unranked"),
    ],
    
    ocr_engine=[
        app_commands.Choice(name="OCR Space (Better text detection)", value="OCR Space"),
        app_commands.Choice(name="EasyOCR", value="EasyOCR"),
        #app_commands.Choice(name="Tesseract OCR", value="Tesseract OCR"),
    ]
)
async def grading(interaction: discord.Interaction, weapon_variant: str, weapon_type: str, riven_rank: str, image: discord.Attachment, platinum: str = None, ocr_engine:str = "OCR Space"):
    # Immediately defer response to prevent expiration
    await interaction.response.defer(thinking=True)

    # Check OCR API status first
    if ocr_engine == "OCR Space":
        is_up, status_embed = await check_ocr_space_api()
        if not is_up:
            await interaction.followup.send(embed=status_embed)  # Use followup instead of response
            await interaction.channel.send("The OCR engine is now set to EasyOCR. Processing...please wait")
            ocr_engine = "EasyOCR"
            # return

    # Check if the uploaded file is an image
    if not (image.content_type and image.content_type.startswith("image/")):
        await interaction.followup.send("Please upload a valid image file!")  # Use followup
        return
    
    # Convert image to JPEG
    global output_riven
    convert_image_to_jpg(image.url, output_riven)
    
    # Get all weapon data (download and save txt file)
    global weapon_data_url
    global file_path
    get_weapon_data(file_path, weapon_data_url)
    
    # Get roll_data
    global sheet_url
    global sheet_path
    get_sheet_data(sheet_path, sheet_url)
    
    # Process the image using OCR API
    if ocr_engine == "OCR Space":
        extracted_text = await ocr_space_file(output_riven)
    else: #ocr_engine == "EasyOCR":
        extracted_text = easy_ocr(output_riven)
    # else:
        # extracted_text = easy_ocr(output_riven)
    # print(extracted_text)
    # return
    if "OCRSpace process failed" in extracted_text:
        await interaction.followup.send(discord.Embed(title="Failed❌", description=extracted_text, color=0xFF0000))
        return
    
    # Check if the image is Riven Mod
    if is_riven(extracted_text) == False:
        await interaction.followup.send("Please upload a Riven Mod image. Make sure to remove any unnecessary text on the Riven Mod details.")  # Use followup
        print(f"is_riven extracted_text : {extracted_text}")
        return
    
    # remove all types of whitespace
    extracted_text = "".join(extracted_text.split())
    print(f"RAW extracted_text : {extracted_text}")
    # return
    # Remove special characters
    extracted_text = re.sub(r"[^a-zA-Z0-9\s\-\.\&\%\,\:]", "", extracted_text)
    
    # Remove unnecessary double line text in riven mod
    extracted_text = re.sub(r"x2forheavyattacks", "", extracted_text, flags=re.IGNORECASE)
    extracted_text = re.sub(r"x2forbows", "", extracted_text, flags=re.IGNORECASE)
    extracted_text = re.sub(r"%[^%]*Heat", "%Heat", extracted_text)
    extracted_text = re.sub(r"%[^%]*Cold", "%Cold", extracted_text) #[^%]*: Matches any sequence of characters except another % (to ensure we're targeting only the closest segment to Cold).
    extracted_text = re.sub(r"%[^%]*Elec", "%Elec", extracted_text)
    extracted_text = re.sub(r"%[^%]*Toxin", "%Toxin", extracted_text)
    extracted_text = extracted_text.replace("%","")
    extracted_text = extracted_text.replace(",",".")
    extracted_text = extracted_text.replace(":",".")
    
    # Use regex to remove dots between numbers and letters
    extracted_text = re.sub(r"(\d)\.(?=[a-zA-Z])", r"\1", extracted_text)
    
    print(f"FILTER extracted_text : {extracted_text}")
    
    # Create an instance of RivenStatDetails
    riven_stat_details = RivenStatDetails()
    
    # Get weapon name and type on riven mod
    weapon_name, weapon_name_found, weapon_type, extracted_text = get_weapon_name(file_path, extracted_text, weapon_type)
    print(f"weapon_name : {weapon_name}")
    if weapon_name_found == False:
        await interaction.followup.send(f"Weapon name not found!\n{extracted_text}")  # Use followup
        return
    
    if weapon_type == "Kitgun":
        await interaction.followup.send(f"{weapon_name} is a Kitgun weapon. Please specify the weapon type manually.")  # Use followup
        return
    
    column_positive = ''
    column_negative = ''
    column_notes = ''
    # Load the Excel file
    if get_type_sentinel_weapon(weapon_name) != "Error":
        df = pd.read_excel("roll_data.xlsx", sheet_name="robotic")  # Load sheet
        column_positive = 'B'
        column_negative = 'E'
        column_notes = 'G'
    elif is_kitgun(weapon_name):
        df = pd.read_excel("roll_data.xlsx", sheet_name="secondary")  # Load sheet
        column_positive = 'B'
        column_negative = 'F'
        column_notes = 'I'
    else:
        if weapon_type == "Rifle" or weapon_type == "Shotgun":
            df = pd.read_excel("roll_data.xlsx", sheet_name="primary")  # Load sheet
            column_positive = 'B'
            column_negative = 'F'
            column_notes = 'I'
        elif weapon_type == "Pistol":
            df = pd.read_excel("roll_data.xlsx", sheet_name="secondary")  # Load sheet
            column_positive = 'B'
            column_negative = 'F'
            column_notes = 'I'
        elif weapon_type == "Melee":
            df = pd.read_excel("roll_data.xlsx", sheet_name="melee")  # Load sheet
            column_positive = 'B'
            column_negative = 'G'
            column_notes = 'J'
        elif weapon_type == "Archgun":
            df = pd.read_excel("roll_data.xlsx", sheet_name="archgun")  # Load sheet
            column_positive = 'B'
            column_negative = 'H'
            column_notes = 'J'
        else:
            print("Failed to load roll_data.xlsx")
    # print(df.head())
    # return
    positive_stats = ""
    negative_stats = ""
    notes = ""
    found = False
    try:
        # Loop through each row
        for index, row in df.iterrows():
            roww, coll = excel_to_pandas(index + 1, 'A')
            temp_name = df.iloc[roww, coll]
            if temp_name.lower() in weapon_name.lower():
                roww, coll = excel_to_pandas(index + 1, column_positive)
                positive_stats = df.iloc[roww, coll]
                roww, coll = excel_to_pandas(index + 1, column_negative)
                negative_stats = df.iloc[roww, coll]
                roww, coll = excel_to_pandas(index + 1, column_notes)
                notes = df.iloc[roww, coll]
                found = True
                break
    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send(f"Error! You may have selected the wrong weapon type. Please double check and try again.")  # Use followup
        return
        
    if pd.isna(notes):
        notes = ""
        
    if found:
        add_text = f"**Recommended rolls for {weapon_name}**\nPositive Stats : {positive_stats}\nNegative Stats : {negative_stats}\n{notes}\n Use `/legend` command for Legend/Key"
    else:
        add_text = f""
    
    # Count buff stat
    extracted_text = extracted_text.lower()
    buff_count, extracted_text, buff_naming = get_buff_count(extracted_text)
    riven_stat_details.BuffCount = buff_count
    # return
    # Get weapon disposition and update weapon name with variant
    weapon_dispo, weapon_name = get_weapon_dispo(file_path, weapon_name, weapon_variant, weapon_type)
    
    if weapon_dispo == 0:
        await interaction.followup.send(f"{weapon_name} disposition not found! Please ensure the input is correct.")  # Use followup
        return
    
    # Get value and stat name
    try:
        get_value_and_stat_name(extracted_text, riven_stat_details)
    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send(f"Error! Failed to retrieve the value and stat name. This may be due to the image being too low in resolution or something obscuring the text. Please retake the screenshot and try again.")  # Use followup
        return
    
    riven_stat_details.StatCount = get_stat_count(riven_stat_details)
    riven_stat_details.CurseCount = riven_stat_details.StatCount - riven_stat_details.BuffCount
    get_riven_type(riven_stat_details)
    
    if riven_stat_details.RivenType == "Unknown Riven Type":
        await interaction.followup.send(f"Unknown Riven Type.\n{extracted_text}")  # Use followup
        print(f" Buff Count : {riven_stat_details.BuffCount}\n Stat Count : {riven_stat_details.StatCount}\n Stat Name : {riven_stat_details.StatName}")
        return
    
    # Stat Name correction
    for i in range(riven_stat_details.StatCount):
        if "Fire Rate" in riven_stat_details.StatName[i] and weapon_type == "Melee":
            riven_stat_details.StatName[i] = "Attack Speed"
    
    # # Value Correction
    # for i in range(riven_stat_details.StatCount):
        # if riven_stat_details.Value[i] > 260 and weapon_dispo < 1 and riven_stat_details.StatName[i] == "Electricity":
            # riven_stat_details.Value[i] -= 104
            # print(f"value correction trigger!")
    
    # Damage to Faction value correction - convert to percentage
    for i in range(riven_stat_details.StatCount):
        damage_to_faction_fix(riven_stat_details, i)
    
    # Get Min Max
    calculate_stats(riven_stat_details, weapon_type, weapon_dispo)
    
    # Divide Min Max by 9 if riven_rank is Unranked
    if riven_rank == "Unranked":
        for i in range(riven_stat_details.StatCount):
            riven_stat_details.Min[i] /= 9
            riven_stat_details.Max[i] /= 9
    
    # Get Prefix and Unit
    get_prefix_and_unit(riven_stat_details)
    
    # Set Grade
    set_grade(riven_stat_details, weapon_type, weapon_dispo, riven_rank)
    
    # Damage to Faction value correction - percentage_to_decimal
    for i in range(riven_stat_details.StatCount):
        percentage_to_decimal(riven_stat_details, i)
    
    # print(f"All value : {riven_stat_details.Value}\nAll Min : {riven_stat_details.Min}\nAll Max : {riven_stat_details.Max}")
    # return
    # Create image grading
    create_grading_image(riven_stat_details, weapon_name, weapon_dispo, image.url, platinum)
    
    # Check if out if range
    out_range, out_range_faction = check_out_range(riven_stat_details)
    
    if out_range == True:
        title_text = "GRADING FAILED ❌"
        description_text = f"There's a stat that is out of range. You may have selected the **wrong weapon variant or riven rank**. If your Riven image is sourced from the **riven.market** or **warframe.market** website, be aware that some Rivens may display incorrect or outdated stats due to older uploads or errors made by the uploader."
    elif out_range == False and out_range_faction == True:
        title_text = "GRADING SUCCESS ✅️"
        description_text = f"Damage to Faction is out of range. You may ignore its grade if the Riven image is from the Warframe mobile app.\n\n{add_text}"
    else:
        title_text = "GRADING SUCCESS ✅️"
        description_text = add_text
    
    embed = discord.Embed(title=title_text, description=description_text, color=discord.Color.purple())
    # Add a footer to the embed
    embed.set_footer(text=f"Tips: Use an in-game image and a maxed-rank Riven mod for optimal grading!")
    # Ensure the image path is valid
    global output_path
    await interaction.followup.send(file=discord.File(output_path), embed=embed)

@client.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {client.user}')

# Run the bot
client.run(TOKEN)
