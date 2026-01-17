import aiohttp
import discord
from discord import app_commands, File
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import requests
import json
import re
import os
from io import BytesIO
import pandas as pd
import uuid
from ultralytics import YOLO
import cv2
import numpy as np
import traceback
from google import genai
from google.genai import types
import random

from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ocr_api = os.getenv("OCR_API")

import asyncio
grading_semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent gradings

# Set up bot with intents
intents = discord.Intents.default()
client = discord.AutoShardedClient(intents=intents)
tree = app_commands.CommandTree(client)

model = YOLO(r"best.pt")
sheet_url = "https://docs.google.com/spreadsheets/d/1zbaeJBuBn44cbVKzJins_E3hTDpnmvOk8heYN-G8yy8/export?format=xlsx"
sheet_path = r"roll_data.xlsx"
weapon_data_url = "https://content.warframe.com/PublicExport/Manifest/ExportWeapons_en.json!00_HjFFOMDv9lQB7M7xv2pTHg"
file_path = r"weapon_data.txt"
background_path = r"bg.png"
font_path = r"segoeuib.ttf"  # Segoe UI Bold font path
# output_riven = r"riven_image.jpg" # Converted riven image JPG path
# output_path = r"riven_grade.png" # Save grade image path
bar_buff_path = r"bar_buff.png"
bar_curse_path = r"bar_curse.png"
all_weapon_name = ""

try:
    gemini_client = genai.Client()
except Exception:
    print("FATAL ERROR: Please set the GEMINI_API_KEY environment variable.")
    gemini_client = None

class RerollView(discord.ui.View):
    def __init__(self, original_message: discord.Message, weapon_name, weapon_type, weapon_variant, original_user, reroll_counter = 0, kuva_cost = 0):
        super().__init__(timeout=180) # Set to None = doesn't expire
        self.original_message = original_message
        self.weapon_name = weapon_name
        self.weapon_type = weapon_type
        self.weapon_variant = weapon_variant
        self.original_user = original_user
        self.reroll_counter = reroll_counter
        self.kuva_cost = kuva_cost
        
    @discord.ui.button(label="New Random", style=discord.ButtonStyle.primary, emoji="♻️")
    async def newrandom_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if interaction.user != self.original_user:
            await interaction.response.send_message("You can only reroll your own commands. Please run **/random** to get your own result.", ephemeral=True)
            return

        # Defer so Discord doesn't timeout while we generate the new image
        await interaction.response.defer()

        task = await random_reroll(interaction, None, None, None)
        
        result = await process_grading(task, new_random=True)
        
        if result is None:
            await interaction.followup.send(
                "Failed to create new random",
                ephemeral=True
            )
            print("\n" + "=" * 34)
            print("|        NEW RANDOM FAILED        |")
            print("=" * 34 + "\n")

            return
        
        new_image_path, new_embed = result
            
        if new_image_path:
            with open(new_image_path, 'rb') as f:
                file = discord.File(f)
                await self.original_message.edit(
                    attachments=[file],
                    embed=new_embed,
                    view=self
                )
        
        ## Update/Reset weapon details for reroll
        self.weapon_name = task.weapon_name
        self.weapon_type = task.weapon_type
        self.weapon_variant = task.weapon_variant
        self.reroll_counter = 0
        self.kuva_cost = 0
        print(f"##### {self.weapon_name} #####")
        
        print("\n" + "=" * 34)
        print("|       NEW RANDOM COMPLETE       |")
        print("=" * 34 + "\n")
    
    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.secondary, emoji="🎲")
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"##### {self.weapon_name} #####")
        if interaction.user != self.original_user:
            await interaction.response.send_message("You can only reroll your own commands. Please run **/random** to get your own result.", ephemeral=True)
            return

        # Defer so Discord doesn't timeout while we generate the new image
        await interaction.response.defer()

        # Get base weapon name (remove variant if present)
        self.weapon_name = get_base_weapon_name(self.weapon_name)
        
        task = await random_reroll(interaction, self.weapon_name, self.weapon_type, self.weapon_variant)
        
        self.reroll_counter += 1
        task.reroll_counter = self.reroll_counter
        
        # Reroll counter and kuva cost
        if task.reroll_counter == 1:
            self.kuva_cost += 900
            task.kuva_cost = self.kuva_cost
        elif task.reroll_counter == 2:
            self.kuva_cost += 1000
            task.kuva_cost = self.kuva_cost
        elif task.reroll_counter == 3:
            self.kuva_cost += 1200
            task.kuva_cost = self.kuva_cost
        elif task.reroll_counter == 4:
            self.kuva_cost += 1400
            task.kuva_cost = self.kuva_cost
        elif task.reroll_counter == 5:
            self.kuva_cost += 1700
            task.kuva_cost = self.kuva_cost
        elif task.reroll_counter == 6:
            self.kuva_cost += 2000
            task.kuva_cost = self.kuva_cost
        elif task.reroll_counter == 7:
            self.kuva_cost += 2350
            task.kuva_cost = self.kuva_cost
        elif task.reroll_counter == 8:
            self.kuva_cost += 2750
            task.kuva_cost = self.kuva_cost
        elif task.reroll_counter == 9:
            self.kuva_cost += 3150  
            task.kuva_cost = self.kuva_cost
        else:
            self.kuva_cost += 3500  
            task.kuva_cost = self.kuva_cost
        
        result = await process_grading(task, is_reroll=True)
        
        if result is None:
            await interaction.followup.send(
                "Failed to reroll",
                ephemeral=True
            )
            print("\n" + "=" * 31)
            print("|        REROLL FAILED        |")
            print("=" * 31 + "\n")

            return
        
        new_image_path, new_embed = result
            
        if new_image_path:
            with open(new_image_path, 'rb') as f:
                file = discord.File(f)
                await self.original_message.edit(
                    attachments=[file],
                    embed=new_embed,
                    view=self
                )
        
        print("\n" + "=" * 31)
        print("|       REROLL COMPLETE       |")
        print("=" * 31 + "\n")
        
    async def on_timeout(self):
        # Disable all components when the view times out
        for item in self.children:
            item.disabled = True
        try:
            await self.original_message.edit(view=self)
        except:
            pass
            
class RegradeView(discord.ui.View):
    def __init__(self, original_message: discord.Message, original_image_path: str, weapon_name: str, buff_count: int, ocr_engine: str, riven_rank: str, platinum: str = None):
        super().__init__(timeout=180)  # 3 minute timeout
        self.original_message = original_message
        self.original_image_path = original_image_path
        self.weapon_name = weapon_name
        self.platinum = platinum
        self.current_variant = "Secondary" if is_kitgun(weapon_name) else "Normal"  # Kitgun default is Secondary
        self.variant = self.current_variant  # Ensure this attribute exist
        self.buff_count = buff_count
        self.ocr_engine = ocr_engine
        self.riven_rank = riven_rank
        
        # Get base weapon name (remove variant if present)
        base_name = get_base_weapon_name(weapon_name)
        
        # Get available variants
        global file_path
        variants = get_available_variants(file_path, base_name)
        
        # Create variant dropdown options
        variant_options = []
        for variant in variants:
            # For Kitguns, use simple Secondary/Primary labels
            if is_kitgun(weapon_name):
                display_name = variant
                value = display_name
            else:
                # Normal variant handling
                if variant == base_name:
                    display_name = "Normal"
                    value = "Normal"
                # Fix for Pangolin
                elif "Pangolin" in variant:
                    display_name = "Prime"
                    value = display_name
                else:
                    display_name = variant.replace(base_name, "").strip()
                    display_name = display_name.replace("-", "")
                    value = display_name
            
            variant_options.append(
                discord.SelectOption(label=display_name, value=value)
            )
            
        # Variant dropdown
        self.variant_select = discord.ui.Select(
            placeholder="Select weapon variant",
            options=variant_options
        )
        self.variant_select.callback = self.on_variant_select
        self.add_item(self.variant_select)
    
    async def on_variant_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.variant = self.variant_select.values[0]
        
        # Check if variant actually changed
        if self.variant == self.current_variant:
            await interaction.followup.send(
                "You selected the same variant. No changes made.",
                ephemeral=True
            )
            return
        
        # Create new grading task with selected variant
        task = GradingTask(
            interaction=interaction,
            weapon_variant=self.variant,
            weapon_type="Auto",
            riven_rank=self.riven_rank,
            image=self.original_image_path,
            platinum=self.platinum,
            ocr_engine=self.ocr_engine,
            buff_count=self.buff_count
        )
        
        # Get the original task's raw_extracted_text if available
        if hasattr(self, 'original_task'):
            task.raw_extracted_text = self.original_task.raw_extracted_text
        
        # Process the grading and get the new image path
        result = await process_grading(task, is_edit=True)
    
        if result is None:
            await interaction.followup.send(
                "Failed to regrade with the selected variant. Please try again.",
                ephemeral=True
            )
            print("\n" + "=" * 34)
            print("|        REGRADING FAILED        |")
            print("=" * 34 + "\n")

            return
        
        new_image_path, new_embed = result
            
        if new_image_path:
            # Update current variant
            self.current_variant = self.variant
            
            # Update dropdown default
            for option in self.variant_select.options:
                option.default = (option.value == self.variant)
            
            with open(new_image_path, 'rb') as f:
                file = discord.File(f)
                await self.original_message.edit(
                    attachments=[file],
                    embed=new_embed,
                    view=self
                )
        
        print("\n" + "=" * 34)
        print("|       REGRADING COMPLETE       |")
        print("=" * 34 + "\n")
        
    async def on_timeout(self):
        # Disable all components when the view times out
        for item in self.children:
            item.disabled = True
        try:
            await self.original_message.edit(view=self)
        except:
            pass

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
        self.Normalize = [0.000] * 4
        self.Highlight = [""] * 4

class GradingTask:
    def __init__(self, interaction, weapon_variant, weapon_type, riven_rank, image, platinum, ocr_engine, buff_count, weapon_name = None, reroll_counter = 0, kuva_cost = 0):
        self.interaction = interaction
        self.weapon_variant = weapon_variant
        self.weapon_type = weapon_type
        self.riven_rank = riven_rank
        self.image = image
        self.platinum = platinum
        self.ocr_engine = ocr_engine
        self.raw_extracted_text = None
        self.buff_count = buff_count
        self.weapon_name = weapon_name
        self.reroll_counter = reroll_counter
        self.kuva_cost = kuva_cost

def special_base_names(extract_text: str, weapon_name: str):
    all_special_base_names = [
        "Dakra Prime","Reaper Prime","Gotva Prime","Euphona Prime","Vadarya Prime","Galariak Prime","Sagek Prime",
        "Tenet Agendus","Tenet Exec","Tenet Grigori","Tenet Livia","Tenet Envoy","Tenet Diplos","Tenet Spirex",
        "Kuva Shildeg","Kuva Bramma","Kuva Chakkhurr","Kuva Twin Stubbas","Kuva Ayanga",
        "Coda Motovore","Coda Bassocyst","Dual Coda Torxica",
        "Dex Dakra","Dex Nikana",
        "Twin Krohkur","Twin Grakatas","Twin Kohmak","Kohmak","Twin Vipers",
        "Dragon Nikana","Mutalist Cernos","Mutalist Quanta","Proboscis Cernos","Dual Skana"
    ]
    
    for wp in all_special_base_names:
        if wp in weapon_name:
            return True, wp
        
        temp_wp = wp.replace(" ", "")
        if temp_wp in extract_text:
            return True, temp_wp
            
    return False, ""
    
def get_base_weapon_name(full_name: str) -> str:
    
    is_special_base_names, wp = special_base_names("", full_name)
    if wp == full_name:
        return full_name
    
    #fix for Pangolin Sword and Prime
    if "Pangolin" in full_name:
        return "Pangolin Sword"
    
    #Fix for Ceti Lacera
    if "Ceti Lacera" in full_name:
        return "Lacera"
    
    #Fix for Prisma Dual Decurions
    if "Prisma Dual Decurions" in full_name:
        return "Dual Decurion"
    # Fix for Twin weapon
        
    """Extracts base weapon name by removing known variant suffixes"""
    variants = ["Prime","Prisma","Wraith","Tenet","Kuva","Coda","Vandal","Rakta","Telos","Vaykor","Sancti","Secura","Synoid","Dex","MK1-"]
    base_name = full_name
        
    for variant in variants:
        if variant in full_name:
            base_name = full_name.replace(variant, "").strip()
            break
    
    return base_name

def get_available_variants(file_path: str, base_weapon_name: str) -> list:
    """
    Returns a list of available variants for a weapon from weapon_data.txt
    Args:
        file_path: Path to weapon_data.txt
        base_weapon_name: The weapon name (e.g., "Braton")
    Returns:
        List of variant names (e.g., ["Braton", "Braton Prime", "Braton Vandal"])
        For Kitguns: ["Secondary", "Primary"]
    """
    try:
        # Special handling for Kitguns
        if is_kitgun(base_weapon_name):
            return ["Secondary", "Primary"]
        
        # Fix for Pangolin
        if "Pangolin" in base_weapon_name:
            return ["Pangolin Sword", "Pangolin Prime"]
            
        # Fix for Cestra
        if "Cestra" == base_weapon_name:
            return ["Cestra"]
        
        # Fix for Bo
        if "Bo" == base_weapon_name:
            return ["Bo", "Bo Prime", "MK1-Bo"]
        
        # Fix for Lacera
        if "Lacera" == base_weapon_name:
            return ["Lacera", "Ceti Lacera"]
            
        data = load_weapon_data(file_path)
        variants = set()
        
        # Check for base name and all variants
        for weapon in data.get("ExportWeapons", []):
            weapon_name = weapon['name']
            
            # Check if weapon matches base name or any variant pattern
            if base_weapon_name in weapon_name:
                is_special_base_names, wp = special_base_names("", weapon_name)
                if not is_special_base_names:
                    variants.add(weapon_name)
                
        # Convert to list and sort with base name first
        variants = sorted(list(variants), key=lambda x: (x != base_weapon_name, x))
        # print(variants)
        return variants
    
    except Exception as e:
        print(f"Error getting variants: {e}")
        return [base_weapon_name]  # Fallback to just the base name

async def get_sheet_data(sheet_path, sheet_url):
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
    
async def resize_large_image(image_path: str, max_size: int = 1920) -> None:
    """Resize an image if its width or height exceeds max_size while maintaining aspect ratio."""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Check if resizing is needed
            if width <= max_size and height <= max_size:
                return
            
            # Calculate new dimensions while maintaining aspect ratio
            if width > height:
                new_width = max_size
                new_height = int((max_size / width) * height)
            else:
                new_height = max_size
                new_width = int((max_size / height) * width)
            
            # --- Anti-Moiré Step ---
            # Applying a very slight blur helps merge pixel gaps before resizing
            if width > max_size or height > max_size:
                img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
            # print("apply blur trigger!")
            # Resize the image
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save the resized image (overwrite original)
            resized_img.save(image_path)
            print(f"Resized image from {width}x{height} to {new_width}x{new_height}")
            
    except Exception as e:
        print(f"Error resizing image: {e}")

async def convert_image_to_jpg(image_path, output_riven):
    try:
        # Open the image file directly
        with Image.open(image_path) as image:
            # Convert and save
            rgb_image = image.convert('RGB')
            rgb_image.save(output_riven, "JPEG")
            await resize_large_image(output_riven)
            print(f"Converted {image_path} to {output_riven}")
            
    except Exception as e:
        print(f"Error converting image: {e}")
        raise

async def gemini_api(filename):
    if not gemini_client:
        return "ERROR: AI client not initialized."
        
    all_stat_name = [
        "Additional Combo Count Chance", "Chance to Gain Combo Count", "Ammo Maximum",
        "Damage to Corpus", "Damage to Grineer", "Damage to Infested",
        "Cold", "Electricity", "Heat","Toxin",
        "Combo Duration","Critical Chance","Critical Chance for Slide Attack","Critical Damage",
        "Damage","Melee Damage","Finisher Damage","Fire Rate","Attack Speed",
        "Projectile Speed","Initial Combo",
        "Impact","Puncture","Slash",
        "Magazine Capacity","Heavy Attack Efficiency","Multishot",
        "Punch Through","Reload Speed","Range","Status Chance","Status Duration",
        "Weapon Recoil","Zoom",
    ]
    
    try:
        # 1. Read the Image Bytes from the local file path
        with open(filename, 'rb') as f:
            image_bytes = f.read()
        
        # 2. Determine the MIME type (Crucial for the API to understand the image format)
        # You'll need to infer this from the file extension (e.g., .png, .jpg)
        mime_type = 'image/png' if filename.lower().endswith('.png') else 'image/jpeg'
        
        # --- REST OF THE LOGIC REMAINS THE SAME ---
        
        # 3. Define the Prompt and Output Instruction
        prompt_text = f"""
        # CRITICAL INSTRUCTION:
        
        1. **Translation & Identification:** Analyze the Riven Mod image. If any Riven-related text (especially the weapon name) is not in English, first translate it to English. Then, determine the official, canonical Warframe weapon name corresponding to the translated text. (e.g., "冷冻光束步枪" -> "Cryo Beam Rifle" -> Official Weapon: Glaxion).
        2. **Weapon Name Verification:** Search for the determined weapon name on the official Warframe Wiki (https://wiki.warframe.com/). If the name exists but differs slightly from the translated name (e.g., if the image says "War Broken" but the wiki uses "Broken War"), replace the weapon name with the official Wiki title.
        3. **Canonical Stat Conversion:** Convert the extracted English stat names to one of the following official canonical names. You **MUST** use a name from this list. If the extracted name is a variation (e.g., "Critical Hit Multiplier"), use the standard name (e.g., "Critical Damage").
        4. **Special Case:** If only "Vinquibus (Melee)" exist in the image, always set the weapon name to "Vinquibusmelee" instead of "Vinquibus".
        **CANONICAL STAT LIST (You MUST use a name from this list for every stat):**
        {", ".join(all_stat_name)}
        
        Analyze the Warframe Riven Mod image.
        
        Extract the following data points:
        1. **Riven Rank** (e.g., 10, 18)
        2. **Weapon Name** (e.g., Cedo)
        3. **Riven Naming** (The words near the weapon name, e.g., Crata-satitis)
        4. **Stat 1 Value and Name** (e.g., 149.9CriticalChance)
        5. **Stat 2 Value and Name** (e.g., 149.9CriticalChance)
        6. **Stat 3 Value and Name** (e.g., 149.9CriticalChance)
        7. **Stat 4 Value and Name** (e.g., 149.9CriticalChance)
        
        **CRITICAL OUTPUT FORMATTING INSTRUCTION:**
        Return ONLY a single, concatenated string. Do not use spaces, or newlines.
        The format must be:
        <riven_rank><weapon_name><riven_naming><stat1_value><stat1_name><stat2_value><stat2_name><stat3_value><stat3_name><stat4_value><stat4_name>

        If a stat is not present (e.g., no 3rd stat, or no 4th stat, or both), omit that part entirely.
        
        Example desired output:
        18CedoCrita-satitis75.8CriticalDamage59Multishot92.3CriticalChance0.83DamagetoInfested
        
        Strictly adhere to this format.
        """

        # 4. Construct the Multimodal Request Parts
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type # Use the inferred MIME type
        )

        # contents = [image_part, types.Part.from_text(prompt_text)]
        contents = [image_part, prompt_text]

        # 5. Call the Gemini API
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents
        )
        
        # 6. Clean and Return the Result
        cleaned_output = response.text.strip().replace(' ', '').replace('+', '')
        
        return cleaned_output

    except FileNotFoundError:
        return f"ERROR: Local file not found at path: {filename}"
    except Exception as e:
        return f"CRITICAL ERROR during API call: {e}"
        
async def ocr_space_file(filename):
    try:
        payload = {
            "isOverlayRequired": False,
            "apikey": ocr_api,
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
                timeout=10  # Timeout after 10 seconds
            )

        # Decode the response and extract "ParsedText"
        response_data = json.loads(r.content.decode())
        
        parsed_results = response_data.get("ParsedResults", [])
        if parsed_results:
            parsed_text = parsed_results[0].get("ParsedText", "")
            return parsed_text  # Return only the parsed text
        else:
            return ""  # Return an empty string if no text is parsed

    except Exception as e:
        print(f"OCRSpace process failed: {e}")   # Handle any exceptions
        return "failed"

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
                        
                        if '<td class="tb_b_right">UP</td>' in status_text:
                            return True, discord.Embed(title="OCR API Status", description="✅ UP", color=0x00FF00)
                        else:
                            return False, discord.Embed(title="OCR API Status", description="❌ DOWN", color=0xFF0000)
                
                return discord.Embed(title="OCR API Status", description="⚠️ Unable to determine status", color=0xFFA500)
        except Exception as e:
            return discord.Embed(title="OCR API Status", description=f"❌ Error: {str(e)}", color=0xFF0000)

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

def get_buff_name(stat_name: str, position: int, buff_count: int) -> str:
    mapping = {
        "Additional Combo Count Chance": {
            2: ["Laci", "nus"],
            3: ["Laci", "-laci", "nus"]
        },
        "Ammo Maximum": {
            2: ["Ampi", "bin"],
            3: ["Ampi", "-ampi", "bin"]
        },
        "Damage to Corpus": {
            2: ["Manti", "tron"],
            3: ["Manti", "-manti", "tron"]
        },
        "Damage to Grineer": {
            2: ["Argi", "con"],
            3: ["Argi", "-argi", "con"]
        },
        "Damage to Infested": {
            2: ["Pura", "ada"],
            3: ["Pura", "-pura", "ada"]
        },
        "Cold": {
            2: ["Geli", "do"],
            3: ["Geli", "-geli", "do"]
        },
        "Combo Duration": {
            2: ["Tempi", "nem"],
            3: ["Tempi", "-tempi", "nem"]
        },
        "Critical Chance for Slide Attack": {
            2: ["Pleci", "nent"],
            3: ["Pleci", "-pleci", "nent"]
        },
        "Critical Chance": {
            2: ["Crita", "cron"],
            3: ["Crita", "-crita", "cron"]
        },
        "Critical Damage": {
            2: ["Acri", "tis"],
            3: ["Acri", "-acri", "tis"]
        },
        "Melee Damage": {
            2: ["Visi", "ata"],
            3: ["Visi", "-visi", "ata"]
        },
        "Electricity": {
            2: ["Vexi", "tio"],
            3: ["Vexi", "-vexi", "tio"]
        },
        "Heat": {
            2: ["Igni", "pha"],
            3: ["Igni", "-igni", "pha"]
        },
        "Finisher Damage": {
            2: ["Exi", "cta"],
            3: ["Exi", "-exi", "cta"]
        },
        "Damage": {
            2: ["Visi", "ata"],
            3: ["Visi", "-visi", "ata"]
        },
        "Fire Rate": {
            2: ["Croni", "dra"],
            3: ["Croni", "-croni", "dra"]
        },
        "Attack Speed": {
            2: ["Chroni", "dra"],
            3: ["Chroni", "-croni", "dra"]
        },
        "Projectile Speed": {
            2: ["Conci", "nak"],
            3: ["Conci", "-conci", "nak"]
        },
        "Initial Combo": {
            2: ["Para", "um"],
            3: ["Para", "-para", "um"]
        },
        "Impact": {
            2: ["Magna", "ton"],
            3: ["Magna", "-magna", "ton"]
        },
        "Magazine Capacity": {
            2: ["Arma", "tin"],
            3: ["Arma", "-arma", "tin"]
        },
        "Heavy Attack Efficiency": {
            2: ["Forti", "us"],
            3: ["Forti", "-forti", "us"]
        },
        "Multishot": {
            2: ["Sati", "can"],
            3: ["Sati", "-sati", "can"]
        },
        "Toxin": {
            2: ["Toxi", "tox"],
            3: ["Toxi", "-toxi", "tox"]
        },
        "Punch Through": {
            2: ["Lexi", "nok"],
            3: ["Lexi", "-lexi", "nok"]
        },
        "Puncture": {
            2: ["Insi", "cak"],
            3: ["Insi", "-insi", "cak"]
        },
        "Reload Speed": {
            2: ["Feva", "tak"],
            3: ["Feva", "-feva", "tak"]
        },
        "Range": {
            2: ["Locti", "tor"],
            3: ["Locti", "-locti", "tor"]
        },
        "Slash": {
            2: ["Sci", "sus"],
            3: ["Sci", "-sci", "sus"]
        },
        "Status Chance": {
            2: ["Hexa", "dex"],
            3: ["Hexa", "-hexa", "dex"]
        },
        "Status Duration": {
            2: ["Deci", "des"],
            3: ["Deci", "-deci", "des"]
        },
        "Weapon Recoil": {
            2: ["Zeti", "mag"],
            3: ["Zeti", "-zeti", "mag"]
        },
        "Zoom": {
            2: ["Hera", "lis"],
            3: ["Hera", "-hera", "lis"]
        },
    }

    if stat_name in mapping:
        if buff_count in mapping[stat_name]:
            if 1 <= position <= len(mapping[stat_name][buff_count]):
                return mapping[stat_name][buff_count][position - 1]

    return ""

def get_buff_naming(riven_stat_details) -> str:
    
    buff_naming = ""
    first = second = third = 0
    
    # Filter out only buffs (exclude the curse)
    buffs = []
    for i in range(riven_stat_details.StatCount):
        # Skip the curse (last stat if it's a curse)
        if i == riven_stat_details.StatCount - 1 and "1 Curse" in riven_stat_details.RivenType:
            continue
        if riven_stat_details.StatName[i] != "":  # Only include valid stats
            buffs.append((riven_stat_details.Normalize[i], riven_stat_details.StatName[i]))

    # Sort by Normalize (highest first)
    buffs.sort(key=lambda x: x[0], reverse=True)

    for pos, (_, stat_name) in enumerate(buffs, start=1):
        buff_naming += get_buff_name(stat_name, pos, riven_stat_details.BuffCount)

    return buff_naming

async def get_weapon_data(file_path: str, weapon_data_url: str):
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
    
    name = get_base_weapon_name(name)
    
    if name == "Akaten":
        return "Melee"
    elif name == "Artax":
        return "Rifle"
    elif name == "Batoten":
        return "Melee"
    elif name == "Burst Laser":
        return "Pistols"
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

def get_weapon_name(file_path: str, extracted_text: str, weapon_type: str, riven_rank:str, weapon_variant:str):
    weapon_name = ""
    weapon_name_found = False
    
    data = load_weapon_data(file_path)
    
    # Dictionary to map incorrect terms to correct ones
    fixes = {
        "Ax-52": "AX-52",
        "Efv-8Mars": "EFV-8Mars",
        "Efv-5Jupiter": "EFV-5Jupiter",
        "VinquibusMelee": "Vinquibusmelee"
    }

    # Apply replacements
    for incorrect, correct in fixes.items():
        extracted_text = extracted_text.replace(incorrect, correct)
        # break
    
    # print(f"extracted_text ============= \n{extracted_text}")
    
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
        
        # variants = ["Prime","Prisma","Wraith","Tenet","Kuva","Coda","Vandal","Rakta","Telos","Vaykor","Sancti","Secura","Synoid","Dex","MK1-"]
        # if weapon_variant in variants:
            # if weapon_variant not in temp_name:
                # continue
        
        # bug fix for Lexi detect as Lex (weapon)
        if temp_name == "Lex":
            index = extracted_text.find("Lex")
            if index + 3 < len(extracted_text):  # Make sure there's a next character
                if extracted_text[index + 3] == "i":
                    print("Found 'Lex' followed by 'i'!")
                    continue
                
        # Remove spaces from the name
        if " " in temp_name:
            temp_name = temp_name.replace(" ", "")
        
        # Fix dual and twin type
        special_fix = special_case_fix(extracted_text)
        if special_fix not in temp_name:
            continue
        
        # Check if special base name
        is_special_base_names, wp = special_base_names(extracted_text, "")
        if is_special_base_names and temp_name == wp:
            weapon_name = weapon['name']
            temp_name = wp
        # Check if the extracted_text contains the temp_name
        elif not is_special_base_names:
            if temp_name in extracted_text or temp_name.title() in extracted_text:
                weapon_name = weapon['name']
        
        if weapon_name != "":
            # Try to identify riven rank if possible
            # Check if "10" or "18" appears right before the weapon name
            if riven_rank == "Auto":
                pattern = rf"(10|18).*{re.escape(temp_name)}"
                match = re.search(pattern, extracted_text)
                if match:
                    number = match.group(1)  # This will be "10" or "18"
                    if number == "10":
                        riven_rank = "Unranked"
                    elif number == "18":
                        riven_rank = "Maxed"
                    print("Riven rank is detected from the Riven mod.")
            
            # Replace the temp_name and text before it in the extracted_text
            if weapon_name == "Lex" and "Lexi" in extracted_text: #bug fix for lex and lexi
                match = re.search(r'(Lex)(?=Lexi)', extracted_text)
                if match:
                    extracted_text = extracted_text[:match.start()] + extracted_text[match.end():]
            else: #other weapon
                extracted_text_copy = extracted_text
                if temp_name in extracted_text:
                    extracted_text = re.sub(r'.*?' + temp_name, '', extracted_text)
                elif temp_name.title() in extracted_text:
                    extracted_text = re.sub(r'.*?' + temp_name.title(), '', extracted_text)
                
            weapon_name_found = True
            
            # For Kitguns, set default type based on variant
            if is_kitgun(weapon_name):
                if weapon_type == "Auto":
                    weapon_type = "Pistols"  # Default to Secondary
                    return weapon_name, weapon_name_found, weapon_type, riven_rank, extracted_text
            
            # Get weapon type
            if weapon_type == "Auto":
                temp_type = weapon['productCategory']
                
                if weapon_name == "Vinquibus":
                    if "Vinquibusmelee" in extracted_text_copy:
                        temp_type = "Melee"
                        
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
                        weapon_type = "Pistols"
                elif temp_type == "Melee":
                    weapon_type = "Melee"
                elif temp_type == "SpaceGuns":
                    weapon_type = "Archgun"
            
            return weapon_name, weapon_name_found, weapon_type, riven_rank, extracted_text
    
    return weapon_name, weapon_name_found, weapon_type, riven_rank, extracted_text  # Return the values if not found

def get_weapon_dispo(file_path: str, weapon_name: str, weapon_variant: str, weapon_type: str):
    weapon_dispo = 0
    data = load_weapon_data(file_path)
    # Combine name with weapon_variant
    weapon_name = combine_with_variant(weapon_name, weapon_variant)
    # print(f"### Weapon Name in getdispo : {weapon_name}")
    for weapon in data.get("ExportWeapons", []):
        if weapon_name == weapon['name']:
            # Updated weapon name with variant
            weapon_name = weapon['name']
            # Get weapon disposition
            if is_kitgun(weapon_name) == True:
                if weapon_type == "Rifle" or weapon_type == "Shotgun":
                    weapon_dispo = weapon['primeOmegaAttenuation']
                elif weapon_type == "Pistols":
                    weapon_dispo = weapon['omegaAttenuation']
            else:
                weapon_dispo = weapon['omegaAttenuation']
            
            return weapon_dispo, weapon_name
    
    return weapon_dispo, weapon_name
    
def combine_with_variant(weapon_name: str, weapon_variant: str) -> str:
    #fix for lacera
    if weapon_variant == "Ceti":
        return "Ceti Lacera"
    
    if is_kitgun(weapon_name):
        return weapon_name
    
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
        numeric_value_match = re.search(r"(\+?\d+(\.\d+)?)", match)
        if numeric_value_match:
            numeric_value = numeric_value_match.group(1)
        else:
            numeric_value = None  # Set None if no numeric value found
        
        temp_name = match[len(numeric_value):]  # The remainder is the stat name
        
        stat_name = get_stat_name(temp_name)
        if stat_name == "can't find stat name":
            stat_name = None  # If not found, set stat_name to None
        
        if numeric_value:
            # Safely store the results in riven_stat_details
            riven_stat_details.Value[i] = float(numeric_value) if numeric_value else 0.0
        else:
            riven_stat_details.Value[i] = 0.0  # Set to 0 if no numeric value
        
        # Only set stat name if it's valid
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

def fix_stat_name(extracted_text: str) -> str:
    # Dictionary of shortforms/aliases → full stat name
    replacements = {
        # Additional Combo Count Chance
        "acc": "Additional Combo Count Chance",
        "accc": "Additional Combo Count Chance",
        "add": "Additional Combo Count Chance",
        "addcombo": "Additional Combo Count Chance",
        "combochance": "Additional Combo Count Chance",

        # Chance to Gain Combo Count
        "gain": "Chance to Gain Combo Count",
        "gcc": "Chance to Gain Combo Count",
        "ctgcc": "Chance to Gain Combo Count",
        "cgcc": "Chance to Gain Combo Count",
        "gaincombo": "Chance to Gain Combo Count",

        # Ammo Maximum
        "am": "Ammo Maximum",
        "ammo": "Ammo Maximum",
        "ammomax": "Ammo Maximum",

        # Attack Speed
        "as": "Attack Speed",
        "atkspd": "Attack Speed",
        "attackspeed": "Attack Speed",

        # Combo Duration
        "combo": "Combo Duration",
        "combodur": "Combo Duration",

        # Cold
        "cold": "Cold",
        "ice": "Cold",

        # Critical Chance
        "cc": "Critical Chance",
        "crit": "Critical Chance",
        "critchance": "Critical Chance",
        "critical": "Critical Chance",
        "cchance": "Critical Chance",
        "critch": "Critical Chance",

        # Critical Chance for Slide Attack
        "slide": "Critical Chance for Slide Attack",
        "slidecrit": "Critical Chance for Slide Attack",
        "slidecc": "Critical Chance for Slide Attack",

        # Critical Damage
        "cd": "Critical Damage",
        "critdmg": "Critical Damage",
        "crtdmg": "Critical Damage",
        "criticaldamage": "Critical Damage",
        "critd": "Critical Damage",
        "critdamage": "Critical Damage",

        # Damage
        "dmg": "Damage",
        "damage": "Damage",

        # Damage to Corpus
        "dtc": "Damage to Corpus",
        "corpus": "Damage to Corpus",

        # Damage to Grineer
        "dtg": "Damage to Grineer",
        "grineer": "Damage to Grineer",

        # Damage to Infested
        "dti": "Damage to Infested",
        "infested": "Damage to Infested",

        # Electricity
        "elec": "Electricity",
        "electric": "Electricity",
        "electricity": "Electricity",
        "shock": "Electricity",

        # Finisher Damage
        "fd": "Finisher Damage",
        "fin": "Finisher Damage",
        "finisher": "Finisher Damage",
        "finisherdmg": "Finisher Damage",
        "fdmg": "Finisher Damage",

        # Fire Rate
        "fr": "Fire Rate",
        "rate": "Fire Rate",
        "firerate": "Fire Rate",

        # Heat
        "heat": "Heat",
        "fire": "Heat",

        # Heavy Attack Efficiency
        "hae": "Heavy Attack Efficiency",
        "eff": "Heavy Attack Efficiency",
        "heavy": "Heavy Attack Efficiency",
        "heavyatk": "Heavy Attack Efficiency",
        "heavyattack": "Heavy Attack Efficiency",

        # Impact
        "impact": "Impact",
        "imp": "Impact",

        # Initial Combo
        "ic": "Initial Combo",
        "initialcombo": "Initial Combo",
        "initcombo": "Initial Combo",
        "init": "Initial Combo",

        # Magazine Capacity
        "mc": "Magazine Capacity",
        "mag": "Magazine Capacity",
        "magazine": "Magazine Capacity",
        "magcap": "Magazine Capacity",

        # Melee Damage
        "md": "Melee Damage",
        "melee": "Melee Damage",
        "meleedmg": "Melee Damage",

        # Multishot
        "ms": "Multishot",
        "multi": "Multishot",
        "multishot": "Multishot",
        "mshot": "Multishot",

        # Projectile Speed
        "ps": "Projectile Speed",
        "pfs": "Projectile Speed",
        "proj": "Projectile Speed",
        "projectile": "Projectile Speed",
        "projspd": "Projectile Speed",

        # Punch Through
        "pt": "Punch Through",
        "punch": "Punch Through",
        "puncthru": "Punch Through",

        # Puncture
        "puncture": "Puncture",
        "punc": "Puncture",

        # Range
        "range": "Range",
        "rng": "Range",

        # Reload Speed
        "rs": "Reload Speed",
        "reload": "Reload Speed",
        "rld": "Reload Speed",
        "rls": "Reload Speed",

        # Slash
        "slash": "Slash",
        "sl": "Slash",

        # Status Chance
        "sc": "Status Chance",
        "status": "Status Chance",
        "statch": "Status Chance",
        "stchance": "Status Chance",

        # Status Duration
        "sd": "Status Duration",
        "statusdur": "Status Duration",
        "statusduration": "Status Duration",
        "stdur": "Status Duration",

        # Toxin
        "tox": "Toxin",
        "toxin": "Toxin",
        "tx": "Toxin",

        # Weapon Recoil
        "wr": "Weapon Recoil",
        "rec": "Weapon Recoil",
        "recoil": "Weapon Recoil",
        "rcl": "Weapon Recoil",

        # Zoom
        "zoom": "Zoom",
    }

    # Split text into tokens (numbers + words can be glued, e.g. "18.6cc")
    tokens = re.findall(r"\d+\.\d+|\d+|[A-Za-z]+", extracted_text)

    fixed_words = []
    for token in tokens:
        key = token.lower()
        if key in replacements:
            fixed_words.append(replacements[key])
        else:
            fixed_words.append(token)

    return " ".join(fixed_words)

def get_stat_name(input_string):
    if "additional" in input_string:
        return "Additional Combo Count Chance"
    elif "gain" in input_string:
        return "Chance to Gain Combo Count"
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
    elif "criticalchancefor" in input_string: # Maybe should "criticalchancefo" instead
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
        return 58.77
    elif stat == "Ammo Maximum":
        if weapon_type == "Rifle":
            return 49.95
        elif weapon_type in ["Shotgun", "Pistols"]:
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
        if weapon_type in ["Rifle", "Pistols"]:
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
        elif weapon_type in ["Shotgun", "Pistols", "Melee"]:
            return 90
        else:
            return 80.1  # Archgun
    elif stat in ["Damage", "Melee Damage"]:
        if weapon_type == "Rifle":
            return 165
        elif weapon_type in ["Shotgun", "Melee"]:
            return 164.7
        elif weapon_type == "Pistols":
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
        elif weapon_type == "Pistols":
            return 74.7
        else:
            return 54.9  # Melee
    elif stat == "Projectile Speed":
        if weapon_type in ["Rifle", "Pistols"]:
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
        elif weapon_type in ["Shotgun", "Pistols"]:
            return 119.7
        else:
            return 60.3  # Archgun
    elif stat == "Punch Through":
        return 2.7
    elif stat == "Reload Speed":
        if weapon_type in ["Rifle", "Pistols"]:
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
        if weapon_type in ["Rifle", "Pistols", "Archgun"]:
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
        return 0.0
        # raise ValueError(f"Base stat ERROR or not exist: {stat}")

def get_riven_rank(riven_stat_details) -> str:
    """
    Determines if a Riven is unranked or maxed by comparing stat values.
    Returns "Unranked" or "Maxed".
    """
    # We need at least one valid stat to check
    valid_stats = 0
    unranked_votes = 0
    maxed_votes = 0
    
    for i in range(riven_stat_details.StatCount):
        if riven_stat_details.StatName[i] == "":
            continue
        
        skip_stat = ["Damage to Infested", "Damage to Corpus", "Damage to Grineer", "Range", "Initial Combo", "Punch Through"]
        
        if riven_stat_details.StatName[i] in skip_stat:
            # Damage to faction needs special handling since values are different
            continue  # Skip these stats for rank detection        
        
        current_value = abs(riven_stat_details.Value[i])
        valid_stats += 1
        
        # Calculate what the value would be if this were an unranked Riven
        potential_maxed_value = current_value * 9
        
        # Check if the scaled value makes sense for a maxed Riven
        # (Most Riven stats fall between ~20% and ~220% when maxed)
        if 15 <= potential_maxed_value <= 240:  # Broad but reasonable range
            unranked_votes += 1
        else:
            maxed_votes += 1
    
    # Need at least one valid stat to make determination
    if valid_stats == 0:
        return "Maxed"  # Default to maxed if we can't determine
    
    # If majority of stats suggest unranked, return unranked
    if unranked_votes > maxed_votes:
        return "Unranked"
    return "Maxed"

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

def get_grade_new(normalize, riven_stat_details, i):
    if -11.5 < normalize <= -9.5:
        return "F"
    elif -9.5 < normalize <= -7.5:
        return "C-"
    elif -7.5 < normalize <= -5.5:
        return "C"
    elif -5.5 < normalize <= -3.5:
        return "C+"
    elif -3.5 < normalize <= -1.5:
        return "B-"
    elif -1.5 < normalize <= 1.5:
        return "B"
    elif 1.5 < normalize <= 3.5:
        return "B+"
    elif 3.5 < normalize <= 5.5:
        return "A-"
    elif 5.5 < normalize <= 7.5:
        return "A"
    elif 7.5 < normalize <= 9.5:
        return "A+"
    elif 9.5 < normalize <= 11.5:
        return "S"
    else:
        if round(riven_stat_details.Min[i] , 1) == riven_stat_details.Value[i]:
            return "F"
        elif riven_stat_details.Value[i] == round(riven_stat_details.Max[i] , 1):
            return "S"
        else:# print("GRADING ERROR. Make sure weapon variant selected is correct")
            return "??"
            
def set_grade_new(riven_stat_details, weapon_type, weapon_dispo, riven_rank):
    for i in range(riven_stat_details.StatCount):
        # if riven_rank == "Unranked":
            # temp_value = riven_stat_details.Value[i] * 9
        # else:
            # temp_value = riven_stat_details.Value[i]
        
        mid_value = (riven_stat_details.Min[i] + riven_stat_details.Max[i]) / 2
        mid_value = round(mid_value, 1)
        # print(f"MID VALUE {i+1} : {mid_value}")
        normalize = (riven_stat_details.Value[i] / mid_value) * 100 - 100
        normalize = round(normalize, 3)
        # print(f"normalize VALUE {i+1} : {normalize}")
        if i == riven_stat_details.StatCount - 1 and "1 Curse" in riven_stat_details.RivenType:
            riven_stat_details.Grade[i] = get_grade_new(-normalize, riven_stat_details, i)
            print(f"Grade Value Curse : {-normalize}")
            riven_stat_details.Normalize[i] = -normalize
        else:
            riven_stat_details.Grade[i] = get_grade_new(normalize, riven_stat_details, i)
            print(f"Grade Value Buff {i+1} : {normalize}")
            riven_stat_details.Normalize[i] = normalize

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
        "F": "#ff0200",
        "??": "#808080"
    }
    
    return grade_colors.get(grade, "White")

async def create_grading_image(riven_stat_details, weapon_name, weapon_dispo, image_file, platinum, weapon_variant, ocr_engine):
    
    wp = weapon_name
    # Set file paths
    global background_path
    global font_path

    # Load the background image
    background = Image.open(background_path)
    
    # Handle image input (could be path or discord.File)
    if isinstance(image_file, str):
        # Input is a file path
        riven_image = Image.open(image_file)
    elif isinstance(image_file, discord.File):
        # Input is discord.File - save to temp file
        temp_path = f"temp_input_{str(uuid.uuid4())[:8]}.jpg"
        with open(temp_path, "wb") as f:
            await image_file.save(f)
        riven_image = Image.open(temp_path)
        os.remove(temp_path)  # Clean up temp file
    else:
        print("Invalid image input type")
        # raise ValueError("Invalid image input type")

    # Resize and position the Riven image
    box_width, box_height = 240, 350
    riven_image.thumbnail((box_width, box_height))
    riven_image_x = 33 + (box_width - riven_image.width) // 2
    riven_image_y = (box_height - riven_image.height) // 2
    
    if ocr_engine == "OCR Space":
        background.paste(riven_image, (riven_image_x, riven_image_y)) # not transparent
    else:
        background.paste(riven_image, (riven_image_x, riven_image_y), riven_image) # transparent
        
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
    if weapon_variant == "Primary": #for kitgun only
        weapon_name = f"{weapon_name} (P)"
    elif weapon_variant == "Secondary": #for kitgun only
        weapon_name = f"{weapon_name} (S)" 
    
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

    # Draw stat names AND highlight
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
    
    # Define your colors
    color1 = (255, 255, 0)
    color2 = (0, 255, 0)
    # Create a master gradient (e.g., 500x100 is usually enough for a stat line)
    master_size = 300
    master_gradient = Image.new("RGBA", (master_size, master_size))
    
    for y in range(master_size):
        for x in range(master_size):
            # 45-degree diagonal math
            progress = (x + y) / (master_size * 2) 
            r = int(color1[0] + (color2[0] - color1[0]) * progress)
            g = int(color1[1] + (color2[1] - color1[1]) * progress)
            b = int(color1[2] + (color2[2] - color1[2]) * progress)
            master_gradient.putpixel((x, y), (r, g, b, 255))
    
    i = 0
    for statname_data in statnames:
        statname_text = statname_data["statname"]
        position = statname_data["position"]
        
        if "999.9" not in statname_text:
            if riven_stat_details.Highlight[i] == "Good":
                # 1. Measure text
                bbox = draw.textbbox((0, 0), statname_text, font=default_font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            
                # Add a tiny bit of padding to prevent cutting off edges
                grad_size = (text_w + 10, text_h + 10)

                # 2. Resize the master gradient to fit this specific text line
                # This ensures the full color range is visible in every stat
                stat_grad = master_gradient.resize(grad_size, Image.LANCZOS)

                # 3. Create the Mask
                mask = Image.new("L", grad_size, 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.text((0, 0), statname_text, fill=255, font=default_font)

                # 4. Paste
                background.paste(stat_grad, position, mask)
            elif riven_stat_details.Highlight[i] == "Bad":
                draw.text(position, statname_text, fill=(255, 75, 75), font=default_font)
            else:
                draw.text(position, statname_text, fill="white", font=default_font)
        i += 1
        
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
    
    # Recreate riven mod - For manual grading only
    if ocr_engine != "OCR Space":
        weapon_name_font_size = 14
        stat_font_size = 12
        dpi = 96
        scaling_factor = dpi / 72
        adjusted_weapon_name_font_size = int(weapon_name_font_size * scaling_factor)
        adjusted_stat_font_size = int(stat_font_size * scaling_factor)
        
        # Create text elements for manual grading recreation
        weapon_name_font = ImageFont.truetype("segoeuib.ttf", adjusted_weapon_name_font_size)
        stat_font = ImageFont.truetype("seguisb.ttf", adjusted_stat_font_size)
        
        buff_naming = get_buff_naming(riven_stat_details)
        wp = get_base_weapon_name(wp)
        weapon_name_buff_naming = f"{wp} {buff_naming}"
        
        combine_stat_1 = str(riven_stat_details.Prefix[0]) + str(riven_stat_details.Value[0]) + str(riven_stat_details.Unit[0] + " " + str(riven_stat_details.StatName[0]))
        combine_stat_2 = str(riven_stat_details.Prefix[1]) + str(riven_stat_details.Value[1]) + str(riven_stat_details.Unit[1] + " " + str(riven_stat_details.StatName[1]))
        combine_stat_3 = str(riven_stat_details.Prefix[2]) + str(riven_stat_details.Value[2]) + str(riven_stat_details.Unit[2] + " " + str(riven_stat_details.StatName[2]))
        combine_stat_4 = str(riven_stat_details.Prefix[3]) + str(riven_stat_details.Value[3]) + str(riven_stat_details.Unit[3] + " " + str(riven_stat_details.StatName[3]))
        stat_details = f"{combine_stat_1}\n{combine_stat_2}\n{combine_stat_3}\n{combine_stat_4}"
        stat_details = stat_details.replace("999.9", "")
        
        # Define text area rectangle (coordinates for where text should be placed on the Riven image)
        text_area_rect = (59, 160, 247, 295)
        left, top, right, bottom = text_area_rect
        rect_width = right - left
        rect_height = bottom - top
        # draw.rectangle(text_area_rect, outline="red", width=1)
        
        # Function to wrap text to fit within specified width
        def wrap_text(text, font, max_width):
            """Wrap text to fit within max_width"""
            lines = []
    
            # If the text contains newlines, process each line separately
            paragraphs = text.split('\n')
    
            for paragraph in paragraphs:
                words = paragraph.split()
                current_line = []
        
                for word in words:
                    # Test if adding this word would exceed the width
                    test_line = ' '.join(current_line + [word])
                    bbox = font.getbbox(test_line)
                    test_width = bbox[2] - bbox[0]
            
                    if test_width <= max_width:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
        
                if current_line:
                    lines.append(' '.join(current_line))
    
            return lines

        # Function to create text image with proper wrapping
        def create_text_image(text_block, fonts, max_width, text_color, bg_color=(0, 0, 0, 0)):
            """Create an image with text that fits within max_width"""
            # Calculate total dimensions needed
            total_height = 0
            line_heights = []
            all_lines = []
    
            for i, text in enumerate(text_block):
                font = fonts[i]
                wrapped_lines = wrap_text(text, font, max_width)
                all_lines.append((wrapped_lines, font))
        
                # Calculate line height for this font
                bbox = font.getbbox("Ay")
                line_height = bbox[3] - bbox[1]
                line_heights.append(line_height)
        
                # Add height for this text element
                total_height += len(wrapped_lines) * line_height * 1.2
        
                # Add spacing between text elements (except after the last one)
                if i < len(text_block) - 1:
                    total_height += line_height * 0.1
    
            # Create transparent image for text
            extra_padding = 5  # Add 10 extra pixels at the bottom
            text_image = Image.new('RGBA', (max_width, int(total_height) + extra_padding), bg_color)
            text_draw = ImageDraw.Draw(text_image)
    
            # Draw text on the temporary image
            y_position = 0
            for i, (wrapped_lines, font) in enumerate(all_lines):
                line_height = line_heights[i]
        
                for line in wrapped_lines:
                    bbox = font.getbbox(line)
                    line_width = bbox[2] - bbox[0]
                    x_position = (max_width - line_width) / 2
                    text_draw.text((x_position, y_position), line, fill=text_color, font=font)
                    y_position += line_height * 1.2
        
                # Add spacing between text elements
                if i < len(all_lines) - 1:
                    y_position += line_height * 0.1
    
            return text_image

        # Create text block with title and description
        text_block = [weapon_name_buff_naming, stat_details]
        fonts = [weapon_name_font, stat_font]

        # Create text image in memory
        text_image = create_text_image(text_block, fonts, rect_width, "#9d6ae9") #9d6ae9 826aa6
        # text_image.save("debug_text_image.png", "PNG")

        # Resize text image if it's taller than the rectangle
        if text_image.height > rect_height:
            # Calculate scaling factor to fit height
            scale_factor = rect_height / text_image.height
            new_width = int(text_image.width * scale_factor)
            new_height = rect_height
            text_image = text_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Calculate position to center the text image within the rectangle
        x_center = left + (rect_width - text_image.width) / 2
        y_center = top + (rect_height - text_image.height) / 2
        
        # Paste the text image onto the main background, centered in the rectangle
        background.paste(text_image, (int(x_center), int(y_center)), text_image)

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
    # global output_path
    output_path = f"riven_image_grade_{str(uuid.uuid4())[:8]}.jpg"
    background = background.convert("RGB")
    background.save(output_path, format="JPEG", dpi=(dpi, dpi))
    return output_path

def bar_resize(min_value: float, max_value: float, value: float) -> float:
    if max_value == min_value:
        return 0.5
    elif value > max_value:
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
        
        if "Damage to" in riven_stat_details.StatName[i]:
            
            if riven_stat_details.Value[i] >= 1:
                if riven_stat_details.Value[i] < riven_stat_details.Min[i] or riven_stat_details.Value[i] > riven_stat_details.Max[i]:
                    out_range_faction = True
            else:
                if riven_stat_details.Value[i] > riven_stat_details.Min[i] or riven_stat_details.Value[i] < riven_stat_details.Max[i]:
                    out_range_faction = True
            
        else:
            if riven_stat_details.Value[i] < round(riven_stat_details.Min[i], 1) or riven_stat_details.Value[i] > round(riven_stat_details.Max[i], 1):
                out_range = True
            
    return out_range, out_range_faction

def non_english_detector(text: str) -> bool:
    """
    Detects if the text contains characters from a non-Latin script (e.g., Cyrillic,
    Chinese) or Latin characters with diacritics (e.g., French, German).

    It effectively ignores numbers, symbols, and non-letter punctuation by focusing
    only on the letters/characters present.

    Args:
        text: The Riven mod text string.

    Returns:
        True if a non-English character/script is detected, False otherwise.
    """
    # 1. Check for Cyrillic script (Russian, Ukrainian)
    # Range: \u0400 to \u04FF
    if re.search(r'[\u0400-\u04FF]', text):
        return True
        
    # 2. Check for CJK (Chinese, Japanese, Korean) characters.
    # This is a broad range covering Han Ideographs, Hiragana, Katakana, and Hangul.
    # Range: \u3040 to \u9FFF and \uAC00 to \uD7AF
    if re.search(r'[\u3040-\u9FFF\uAC00-\uD7AF]', text):
        return True

    # 3. Check for common accented Latin characters (Diacritics).
    # These are used in many Latin-based Warframe languages (French, German, Spanish, etc.)
    # Examples: á, é, ü, ñ, ç, ß
    if re.search(r'[áéíóúÁÉÍÓÚñÑüÜäöüÄÖÜßçÇèÉÊËëïîôœùûŸ]', text):
        return True
    
    # If the text contains only unaccented Latin letters, spaces, numbers, and common symbols,
    # the function returns False. It assumes the text is English (or a Latin language
    # using no/few accents, which is too complex to determine without a dictionary).
    return False

async def random_reroll(interaction, name:str, weapon_type:str = None, weapon_variant:str = None):
    
    try:
        # GET RANDOM WEAPON NAME
        if name:
            for w in all_weapon_name:
                if w["name"] == name:
                    name = w["name"]
                    category = w["category"]
        else:
            random_weapon = random.choice(all_weapon_name)
            name = random_weapon["name"]
            category = random_weapon["category"]
        # name = "Laetum"
        # category = "Pistols"
        print(f"### Random Pick Name  : {name}")
        print(f"### Category : {category}\n")
        
        if is_kitgun(name) == False and weapon_variant == None:
            weapon_type = category
        
        ## FIX WEAPON TYPE
        # slot = random.choice(kitguns_variant)
        if is_kitgun(name) and weapon_type == None:
            kitguns_variant = ["Primary", "Secondary"]
            weapon_variant = random.choice(kitguns_variant)
            print(f"### Random Pick Variant Kitgun  : {weapon_variant}")
            if weapon_variant == "Primary":
                if name == "Catchmoon":
                    weapon_type = "Shotgun"
                elif name == "Sporelacer":
                    weapon_type = "Shotgun"
                else:
                    weapon_type = "Rifle"
            elif weapon_variant == "Secondary":
                weapon_type = "Pistols"
        
        ## Fix for shotgun    
        if weapon_type == "LongGuns":
            if is_shotgun(name):
                weapon_type = "Shotgun"
            else:
                weapon_type = "Rifle"
        ## Fix for Archwing gun
        if weapon_type == "SpaceGuns":
            weapon_type = "Archgun"
        
        ## Fix for Zaw
        if is_zaw(name):
            weapon_type = "Melee"
            
        ## Fix for SentinelWeapons
        if weapon_type == "SentinelWeapons":
            weapon_type = get_type_sentinel_weapon(name)
        
        # GET BEST VARIANT AND DISPO OF WEAPON
        # weapon_variant = "Prime"
        is_special_base_names, wp = special_base_names("",name)
        if weapon_variant == None and not is_special_base_names:
            variants = get_available_variants(file_path, name)
            print(f"## Variant Available : {variants} ##")
            lowest_dispo = 99
            lowest_name = "Random Name"
            
            if len(variants) > 1:
                for v in variants:
                    # get weapon disposition
                    # remove base name in v
                    # print(f"v before : {v}")
                    if v == name:
                        v = "Normal"
                    # Fix for Pangolin
                    elif "Pangolin" in v:
                        v = "Prime"
                    else:
                        v = v.replace(name, "").strip()
                        v = v.replace("-", "")
                        # print(f"v after : {v}")
                    
                    weapon_dispo, new_name = get_weapon_dispo(file_path, name, v, weapon_type)
                
                    if weapon_dispo < lowest_dispo:
                        print(f" Lowest Dispo updated from {lowest_dispo} to {weapon_dispo}")
                        lowest_dispo = weapon_dispo
                        lowest_name = new_name
                        lowest_variant = v
                    elif weapon_dispo == lowest_dispo and "Prime" in new_name:
                        print(f" Lowest Dispo updated from {lowest_dispo} to {weapon_dispo}")
                        lowest_dispo = weapon_dispo
                        lowest_name = new_name
                        lowest_variant = v
            
                print(f" Lowest Dispo : {lowest_dispo}")
                print(f" Lowest Name : {lowest_name}")
                weapon_dispo = lowest_dispo
                name = lowest_name
                weapon_variant = lowest_variant
            else:
                weapon_dispo, new_name = get_weapon_dispo(file_path, name, weapon_variant, weapon_type)
        else: # for reroll
            # get weapon disposition
            weapon_dispo, name = get_weapon_dispo(file_path, name, weapon_variant, weapon_type)
        
        # print(f"## Name for Dispo : {name} ##")
        # print(f"## Variant for Dispo : {weapon_variant} ##")
        # print(f"## Weapon Type for Dispo : {weapon_type} ##")
        
        # GET RANDOM RIVEN TYPE
        riven_type = ["2 Buff 0 Curse","2 Buff 1 Curse","3 Buff 0 Curse","3 Buff 1 Curse",]
        pick_riven_type = random.choice(riven_type)
        if pick_riven_type == "2 Buff 0 Curse":
            buff = 2
            curse = 0
        elif pick_riven_type == "2 Buff 1 Curse":
            buff = 2
            curse = 1
        elif pick_riven_type == "3 Buff 0 Curse":
            buff = 3
            curse = 0
        else: # 3 Buff 1 Curse
            buff = 3
            curse = 1
        
        StatCount = buff + curse
        
        # GET RANDOM STAT NAME
        # Shared stats (Elemental, Faction damage, etc.)
        generic_stats = [
            "Damage to Corpus", "Damage to Grineer", "Damage to Infested",
            "Cold", "Electricity", "Heat", "Toxin", "Status Chance", "Status Duration",
            "Critical Chance", "Critical Damage",
            "Impact", "Puncture", "Slash"
        ]

        # Ranged only (Rifles, Pistols, Shotguns)
        ranged_stats = [
            "Ammo Maximum", "Damage",
            "Fire Rate", "Projectile Speed", "Magazine Capacity", "Multishot", 
            "Punch Through", "Reload Speed", "Weapon Recoil", "Zoom"
        ]

        # Melee only
        melee_stats = [
            "Additional Combo Count Chance", 
            "Combo Duration", "Melee Damage", 
            "Finisher Damage", "Attack Speed", "Initial Combo", 
            "Heavy Attack Efficiency", "Range"
        ]
        
        # Malus Melee only
        # exclusive = "Chance to Gain Combo Count"
        
        elements = ["Cold", "Electricity", "Heat", "Toxin"]
        
        physicals = ["Impact", "Puncture", "Slash"]
        
        if weapon_type == "Melee":
            pool = generic_stats + melee_stats
            # if "1 Curse" in pick_riven_type:
                # pool.append(exclusive)
        else:
            pool = generic_stats + ranged_stats
            
        # Check IPS
        all_damage = []
        data = load_weapon_data(file_path)
        for weapon in data.get("ExportWeapons", []):
            temp_name = weapon['name']
            if temp_name == name:
                all_damage = weapon['damagePerShot']
                break
        
        if all_damage[0] == 0:
            pool.remove("Impact")
            print(f"Impact has been removed from pool")
        if all_damage[1] == 0:
            pool.remove("Puncture")
            print(f"Puncture has been removed from pool")
        if all_damage[2] == 0:
            pool.remove("Slash")
            print(f"Slash has been removed from pool")
            
        # # Melee Damage should never be curse stat
        # if "1 Curse" in pick_riven_type and weapon_type == "Melee":
            # pool.remove("Melee Damage")
            # print(f"Melee Damage has been removed from pool")
        
        if "1 Curse" in pick_riven_type:
            # Pick the BUFFS first (all stats except the last one)
            # We pick (StatCount - 1) stats from the full pool
            buffs = random.sample(pool, StatCount - 1)
            
            # Create a CURSE POOL that has no elements AND no stats already picked as buffs
            # curse_pool = [s for s in pool if s not in elements and s not in buffs]
            curse_pool = []
            for s in pool:
                if s not in elements and s not in buffs:
                    if weapon_type == "Melee" and s != "Melee Damage": # Melee Damage never be curse stat
                        curse_pool.append(s)
                    if weapon_type != "Melee":
                        curse_pool.append(s)
            
            # Pick the 1 CURSE
            if curse_pool:
                curse = random.sample(curse_pool, 1)
                selected_stats = buffs + curse
            else:
                # Fallback if curse_pool is empty
                selected_stats = buffs + random.sample([s for s in pool if s not in buffs], 1)
                
            # Fix stat name if Malus
            if weapon_type == "Melee" and selected_stats[-1] == "Additional Combo Count Chance":
                selected_stats[-1] = "Chance to Gain Combo Count"
        else:
            # If no curse, just pick normally
            selected_stats = random.sample(pool, StatCount)
        
        # "Exclusive" move-to-back logic
        # change Additional Combo Count Chance to Chance to Gain Combo Count if melee and malus stat
        # if exclusive in selected_stats:
            # selected_stats.remove(exclusive)
            # selected_stats.append(exclusive)
        
        while len(selected_stats) < 4:
            selected_stats.append("")
        
        # GET RANDOM VALUE
        # get min max
        pick_value = [999.9] * 4
        
        if pick_riven_type == "2 Buff 0 Curse":
            
            base_stat = get_base_stat(selected_stats[0], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 0.99)
            max = calculate_max(base_stat, weapon_dispo, 0.99)
            pick_value[0] = round(random.uniform(min, max), 1)
            
            base_stat = get_base_stat(selected_stats[1], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 0.99)
            max = calculate_max(base_stat, weapon_dispo, 0.99)
            pick_value[1] = round(random.uniform(min, max), 1)
                
        elif pick_riven_type == "2 Buff 1 Curse":
            
            base_stat = get_base_stat(selected_stats[0], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 1.2375)
            max = calculate_max(base_stat, weapon_dispo, 1.2375)
            pick_value[0] = round(random.uniform(min, max), 1)
            
            base_stat = get_base_stat(selected_stats[1], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 1.2375)
            max = calculate_max(base_stat, weapon_dispo, 1.2375)
            pick_value[1] = round(random.uniform(min, max), 1)
            
            base_stat = get_base_stat(selected_stats[2], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, -0.495)
            max = calculate_max(base_stat, weapon_dispo, -0.495)
            pick_value[2] = round(random.uniform(min, max), 1)
            
        elif pick_riven_type == "3 Buff 0 Curse":
            
            base_stat = get_base_stat(selected_stats[0], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 0.75)
            max = calculate_max(base_stat, weapon_dispo, 0.75)
            pick_value[0] = round(random.uniform(min, max), 1)

            base_stat = get_base_stat(selected_stats[1], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 0.75)
            max = calculate_max(base_stat, weapon_dispo, 0.75)
            pick_value[1] = round(random.uniform(min, max), 1)

            base_stat = get_base_stat(selected_stats[2], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 0.75)
            max = calculate_max(base_stat, weapon_dispo, 0.75)
            pick_value[2] = round(random.uniform(min, max), 1)

        else: # 3 Buff 1 Curse
            
            base_stat = get_base_stat(selected_stats[0], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 0.9375)
            max = calculate_max(base_stat, weapon_dispo, 0.9375)
            pick_value[0] = round(random.uniform(min, max), 1)

            base_stat = get_base_stat(selected_stats[1], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 0.9375)
            max = calculate_max(base_stat, weapon_dispo, 0.9375)
            pick_value[1] = round(random.uniform(min, max), 1)

            base_stat = get_base_stat(selected_stats[2], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, 0.9375)
            max = calculate_max(base_stat, weapon_dispo, 0.9375)
            pick_value[2] = round(random.uniform(min, max), 1)

            base_stat = get_base_stat(selected_stats[3], weapon_type)
            min = calculate_min(base_stat, weapon_dispo, -0.75)
            max = calculate_max(base_stat, weapon_dispo, -0.75)
            pick_value[3] = round(random.uniform(min, max), 1)
        
        print(f"## Weapon Name : {name} ##")
        print(f"## Weapon Type : {weapon_type} ##")
        print(f"## Weapon Variant : {weapon_variant} ##")
        
        # Create a task with the mock image path
        task = GradingTask(
            interaction=interaction,
            weapon_variant=weapon_variant,
            weapon_type=weapon_type,
            riven_rank="Auto",
            image="empty_riven_maxed.png",
            platinum=None,
            ocr_engine="Random",
            buff_count = buff,
            weapon_name = name
        )
        
        extracted_text = f"18{name}{pick_value[0]}{selected_stats[0]}{pick_value[1]}{selected_stats[1]}{pick_value[2]}{selected_stats[2]}{pick_value[3]}{selected_stats[3]}"     
        extracted_text = extracted_text.replace("999.9","")
        extracted_text = extracted_text.replace("None","")
        
        # Store the manually created text
        task.raw_extracted_text = extracted_text
        
        return task
    
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"```{e}```")
    
async def process_grading(task: GradingTask, is_edit: bool = False, is_reroll: bool = False, new_random: bool = False, first_random: bool = False):
    async with grading_semaphore:  # This limits concurrent executions
        
        print("\n" + "=" * 26)
        print("|        STARTING        |")
        print("=" * 26 + "\n")
        
        # if is_edit == False:    
            # print("\n" + "=" * 34)
            # print("|        STARTING GRADING        |")
            # print("=" * 34 + "\n")
        # elif is_reroll == True:
            # print("\n" + "=" * 34)
            # print("|        REROLLING        |")
            # print("=" * 34 + "\n")
        # else:
            # print("\n" + "=" * 34)
            # print("|       STARTING REGRADING       |")
            # print("=" * 34 + "\n")

        try:  
            # Skip image processing for manual grading
            if task.ocr_engine == "OCR Space":
                output_riven = f"riven_image_{str(uuid.uuid4())[:8]}.jpg"
                await convert_image_to_jpg(task.image, output_riven)
            else:
                output_riven = task.image
    
            # Get all weapon data (download and save txt file)
            global weapon_data_url
            global file_path
            await get_weapon_data(file_path, weapon_data_url)
    
            # Get roll_data
            global sheet_url
            global sheet_path
            await get_sheet_data(sheet_path, sheet_url)
    
            # Process the image using OCR API
            # Skip OCR if raw_extracted_text already exists (regrade case)
            if task.raw_extracted_text is None:
                # Process the image using OCR API
                if task.ocr_engine == "OCR Space":
                    print(f"OCR Space detection used...")
                    extracted_text = await ocr_space_file(output_riven)
                    # extracted_text = "failed"
                    
                    non_english = False
                    if non_english_detector(extracted_text) == True:
                        non_english = True
                        print(f"Non-english detected")
                        print(f"OCR Space result : {extracted_text}")
                    
                    # Use Gemini if OCRSpace is unavailable
                    if extracted_text == "failed" or non_english == True:
                        print(f"Gemini detection used...")
                        counter = 0
                        while True:
                            extracted_text = await gemini_api(output_riven)
                            if "ERROR" not in extracted_text:
                                break
                            counter+=1
                            
                            if counter == 4:
                                extracted_text = "Limit Reached"
                                break
                            
                            print(f"{counter} , retrying....")
                            await asyncio.sleep(5)    
                        
                    task.raw_extracted_text = extracted_text  # Store the raw OCR result
                print(f"RAW extracted_text : {extracted_text}")
            else:
                extracted_text = task.raw_extracted_text  # Use stored OCR result for regrade
                print(f"Using stored OCR result for regrade: {extracted_text}")
                
            if extracted_text == "failed":
                await task.interaction.followup.send(embed=discord.Embed(title="OCR API Status",description="❌ Down!",color=discord.Color.red()))
                await task.interaction.channel.send("Please try again later, or use manual grading instead. [(how to?)](https://discord.com/channels/1350251436977557534/1350258178998276147/1410190204551041117)")
                return
            # extracted_text = "Limit Reached"
            if extracted_text == "Limit Reached":
                await task.interaction.followup.send(embed=discord.Embed(title="Secondary OCR API Status",description="❌ The limit have been reached! (20 requests per day)",color=discord.Color.red()).set_footer(text="Secondary OCR API is only used when the main OCR API is unavailable."))
                await task.interaction.channel.send("Please try again later, or use manual grading instead. [(how to?)](https://discord.com/channels/1350251436977557534/1350258178998276147/1410190204551041117)")
                #await task.interaction.channel.send("▶ If the riven is English text, try again later. The main OCR API is usually down for just a few minutes.\n▶ If the riven has **NON-ENGLISH** text, try again tomorrow (Reset at midnight Pacific Time) **OR** grade now using manual grading instead. [(how to?)](https://discord.com/channels/1350251436977557534/1350258178998276147/1410190204551041117)")
                return
            # return
    
            # Check if the text represents a Riven Mod (skip for manual)
            if task.ocr_engine == "OCR Space" and is_riven(extracted_text) == False:
                await task.interaction.followup.send("Please upload an image containing only one visible Riven Mod. Do not include any extra text, only the Riven Mod itself.", file=discord.File(output_riven))  # Use followup
                print(f"is_riven extracted_text : {extracted_text}")
                return
            
            # Replace a space with a dot only if there are numbers on both sides of the space
            extracted_text = re.sub(r'(\d)\s+(\d)', r'\1.\2', extracted_text)
            
            # remove all types of whitespace
            extracted_text = "".join(extracted_text.split())
            #print(f"RAW extracted_text : {extracted_text}")
            # return
            # Remove special characters except this
            extracted_text = re.sub(r"[^a-zA-Z0-9\s\-\.\&\%\,\:\']", "", extracted_text)

            # Remove unnecessary text in riven mod
            extracted_text = re.sub(r"x2forheavyattacks", "", extracted_text, flags=re.IGNORECASE)
            extracted_text = re.sub(r"x2forbows", "", extracted_text, flags=re.IGNORECASE)
            extracted_text = re.sub(r"%[^%]*Heat", "%Heat", extracted_text)
            extracted_text = re.sub(r"%[^%]*Cold", "%Cold", extracted_text)
            extracted_text = re.sub(r"%[^%]*Elec", "%Elec", extracted_text)
            extracted_text = re.sub(r"%[^%]*Toxin", "%Toxin", extracted_text)
            extracted_text = re.sub(r"%[^%]*Impact", "%Impact", extracted_text)
            extracted_text = re.sub(r"%[^%]*Puncture", "%Puncture", extracted_text)
            extracted_text = re.sub(r"%[^%]*Slash", "%Slash", extracted_text)
            extracted_text = extracted_text.replace("--","-")
            extracted_text = extracted_text.replace("Gell","Geli")
            extracted_text = extracted_text.replace("gell","geli")
            extracted_text = extracted_text.replace("cion","cron")
            extracted_text = extracted_text.replace("%","")
            extracted_text = extracted_text.replace(",",".")
            extracted_text = extracted_text.replace("'",".")
            extracted_text = extracted_text.replace(":",".")
    
            # Use regex to remove dots between numbers and letters
            extracted_text = re.sub(r"(\d)\.(?=[a-zA-Z])", r"\1", extracted_text)
    
            print(f"FILTER extracted_text : {extracted_text}")
    
            # Create an instance of RivenStatDetails
            riven_stat_details = RivenStatDetails()
            
            # Get weapon name and type on riven mod. Also riven rank if possible
            weapon_name, weapon_name_found, task.weapon_type, task.riven_rank, extracted_text = get_weapon_name(file_path, extracted_text, task.weapon_type, task.riven_rank, task.weapon_variant)
            print(f"weapon_name : {weapon_name}")
            if weapon_name_found == False:
                if task.ocr_engine == "OCR Space":
                    await task.interaction.followup.send(
                        f"**Weapon name not found!**\n"
                        f"▶ Ensure all Riven Mod details are fully visible and not obscured.\n"
                        f"▶ If using a phone camera, avoid taking photos too close to the screen. Visible pixels or '[moire patterns](<https://www.google.com/search?q=what+is+moire+patterns>)' can interfere with detection.\n\n"
                        f"**Detected Text:**\n`{extracted_text}`", 
                        file=discord.File(output_riven)
)                    # os.remove(output_riven)
                    return
                else:
                    await task.interaction.followup.send(f"Weapon name not found! Please make sure to select the weapon name from the autocomplete suggestions.\n{extracted_text}")  # Use followup
                    # os.remove(output_riven)
                    return
            
            # For Kitguns, set weapon type based on selected variant
            if is_kitgun(weapon_name) and task.weapon_type not in ["Primary","Secondary"]:
                # if is_edit == False:
                    # task.weapon_variant = "Secondary"
                
                if task.weapon_variant == "Primary":
                    if weapon_name == "Catchmoon":
                        task.weapon_type = "Shotgun"
                    elif weapon_name == "Sporelacer":
                        task.weapon_type = "Shotgun"
                    else:
                        task.weapon_type = "Rifle"
                elif task.weapon_variant == "Secondary":  # Secondary
                    task.weapon_type = "Pistols"
            
            if is_kitgun(weapon_name) and is_edit == False and first_random == False and is_reroll == False and new_random == False:
                task.weapon_variant = "Secondary"
                
            # if is_kitgun(weapon_name) and task.weapon_type not in ["Primary","Secondary"] and is_edit == False:
                # task.weapon_variant = "Secondary"
                
            print(f"weapon_type : {task.weapon_type}")
            
            if task.weapon_type == "Kitgun":
                await task.interaction.followup.send(f"{weapon_name} is a Kitgun weapon. Kitguns are currently not supported for grading—this is temporary.")  # Use followup
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
                if task.weapon_type == "Rifle" or task.weapon_type == "Shotgun":
                    df = pd.read_excel("roll_data.xlsx", sheet_name="primary")  # Load sheet
                    column_positive = 'B'
                    column_negative = 'F'
                    column_notes = 'I'
                elif task.weapon_type == "Pistols":
                    df = pd.read_excel("roll_data.xlsx", sheet_name="secondary")  # Load sheet
                    column_positive = 'B'
                    column_negative = 'F'
                    column_notes = 'I'
                elif task.weapon_type == "Melee":
                    df = pd.read_excel("roll_data.xlsx", sheet_name="melee")  # Load sheet
                    column_positive = 'B'
                    column_negative = 'G'
                    column_notes = 'J'
                elif task.weapon_type == "Archgun":
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
            base_name = get_base_weapon_name(weapon_name)
            try:
                # Loop through each row
                for index, row in df.iterrows():
                    roww, coll = excel_to_pandas(index + 1, 'A')
                    temp_name = df.iloc[roww, coll]
                    if temp_name.lower() in base_name.lower():
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
                await task.interaction.followup.send(f"Error! You may have selected the wrong weapon type. Please double check and try again.")  # Use followup
                return
        
            if pd.isna(notes):
                notes = ""
        
            if found:
                add_text = f"**Recommended rolls for {temp_name.title()}** [(source)](https://docs.google.com/spreadsheets/d/1zbaeJBuBn44cbVKzJins_E3hTDpnmvOk8heYN-G8yy8)\nPositive Stats : {positive_stats}\nNegative Stats : {negative_stats}\n{notes}\n Use `/legend` command for Legend/Key"
            else:
                add_text = f""
            
            # Count buff stat
            extracted_text = extracted_text.lower()
            if task.ocr_engine == "OCR Space":
                buff_count, extracted_text, buff_naming = get_buff_count(extracted_text)
                riven_stat_details.BuffCount = buff_count
            else:
                riven_stat_details.BuffCount = task.buff_count
            # return
            # Get weapon disposition and update weapon name with variant
            weapon_dispo, weapon_name = get_weapon_dispo(file_path, weapon_name, task.weapon_variant, task.weapon_type)
            
            if weapon_dispo == 0:
                await task.interaction.followup.send(f"{weapon_name} disposition not found! Please ensure the input is correct.")  # Use followup
                return
            
            # Update Vinquibus name if melee
            if weapon_name == "Vinquibus" and task.weapon_type == "Melee":
                weapon_name = "Vinquibus (Melee)"
            
            # Get value and stat name
            try:
                get_value_and_stat_name(extracted_text, riven_stat_details)
            except Exception as e:
                print(f"Error: {e}")
                await task.interaction.followup.send(f"Error! Failed to retrieve the value and stat name. This may be due to the image being too low in resolution or something obscuring the text. Please retake the screenshot and try again.")  # Use followup
                return
            
            riven_stat_details.StatCount = get_stat_count(riven_stat_details)
            riven_stat_details.CurseCount = riven_stat_details.StatCount - riven_stat_details.BuffCount
            get_riven_type(riven_stat_details)
            # print(f"Riven Type : {riven_stat_details.RivenType}")
            if riven_stat_details.RivenType == "Unknown Riven Type":
                await task.interaction.followup.send(f"Unknown Riven Type.\n{extracted_text}", file=discord.File(output_riven))  # Use followup
                print(f" Buff Count : {riven_stat_details.BuffCount}\n Stat Count : {riven_stat_details.StatCount}\n Stat Name : {riven_stat_details.StatName}")
                return
            
            # Stat Name correction
            for i in range(riven_stat_details.StatCount):
                if "Fire Rate" in riven_stat_details.StatName[i] and task.weapon_type == "Melee":
                    riven_stat_details.StatName[i] = "Attack Speed"
    
            # # Value Correction
            # for i in range(riven_stat_details.StatCount):
                # if riven_stat_details.Value[i] > 260 and weapon_dispo < 1 and riven_stat_details.StatName[i] == "Electricity":
                    # riven_stat_details.Value[i] -= 104
                    # print(f"value correction trigger!")

            # Damage to Faction value correction - convert to percentage
            for i in range(riven_stat_details.StatCount):
                # Only process if value is not percentage
                if "Damage to" in riven_stat_details.StatName[i] and riven_stat_details.Value[i] < 3:
                    damage_to_faction_fix(riven_stat_details, i)

            # print(f"riven_stat_details value : {riven_stat_details.Value}")
            # print(f"riven_stat_details stat name : {riven_stat_details.StatName}")
            
            # Define the mapping of Full Name -> Shortform
            stat_map = {
                "Attack Speed": ["AS"], 
                "Cold": ["COLD", "ELEMENT"], 
                "Critical Chance": ["CC"],
                "Critical Chance for Slide Attack": ["SLIDE"], 
                "Critical Damage": ["CD"],
                "Damage": ["DMG"], 
                "Melee Damage": ["DMG"], 
                "Damage to Corpus": ["DTC"],
                "Damage to Grineer": ["DTG"], 
                "Damage to Infested": ["DTI"],
                "Electricity": ["ELEC", "ELEMENT"], 
                "Finisher Damage": ["FIN"], 
                "Fire Rate": ["FR"],
                "Heat": ["HEAT", "ELEMENT"], 
                "Heavy Attack Efficiency": ["EFF"], 
                "Impact": ["IMP"],
                "Initial Combo": ["IC"], 
                "Magazine Capacity": ["MAG"], 
                "Multishot": ["MS"],
                "Projectile Speed": ["PFS"], 
                "Punch Through": ["PT"], 
                "Puncture": ["PUNC"],
                "Range": ["RANGE"], 
                "Reload Speed": ["RLS"], 
                "Slash": ["SLASH"],
                "Status Chance": ["SC"], 
                "Status Duration": ["SD"], 
                "Toxin": ["TOX", "ELEMENT"],
                "Weapon Recoil": ["REC"], 
                "Zoom": ["ZOOM"]
            }

            # Highlight Stats logic
            for i in range(riven_stat_details.StatCount):
                current_stat = riven_stat_details.StatName[i]
    
                # Get the shortform from our map (returns None if not found)
                shortforms = stat_map.get(current_stat)
                
                if not shortforms:
                    continue
                
                for code in shortforms:
                    # Check if the shortform exists in either positive or negative lists
                    if code in positive_stats:
                        riven_stat_details.Highlight[i] = "Good"
                        if riven_stat_details.RivenType == "2 Buff 1 Curse" and i == 2:
                            riven_stat_details.Highlight[i] = "Bad"
                        elif riven_stat_details.RivenType == "3 Buff 1 Curse" and i == 3:
                            riven_stat_details.Highlight[i] = "Bad"
                        
                    # Highligh for curse
                    if code in negative_stats:
                        if riven_stat_details.RivenType == "2 Buff 1 Curse" and i == 2:
                            riven_stat_details.Highlight[i] = "Good"
                        elif riven_stat_details.RivenType == "3 Buff 1 Curse" and i == 3:
                            riven_stat_details.Highlight[i] = "Good"
                            
                    # Default red highlight for curse
                    elif code in ["DMG","CC","CD","MS","SC"]:
                        if riven_stat_details.RivenType == "2 Buff 1 Curse" and i == 2:
                            riven_stat_details.Highlight[i] = "Bad"
                        elif riven_stat_details.RivenType == "3 Buff 1 Curse" and i == 3:
                            riven_stat_details.Highlight[i] = "Bad"
                            
            # Get Min Max
            calculate_stats(riven_stat_details, task.weapon_type, weapon_dispo)
            
            # Get rank rand Divide Min Max by 9 if riven_rank is Unranked
            if task.riven_rank == "Auto":
                task.riven_rank = get_riven_rank(riven_stat_details)
                print("Riven rank has been predicted based on the stat values.")
                
            if task.riven_rank == "Unranked":
                for i in range(riven_stat_details.StatCount):
                    riven_stat_details.Min[i] /= 9
                    riven_stat_details.Max[i] /= 9
                    
            print(f"riven rank : {task.riven_rank}")
            
            if task.ocr_engine == "Manual":
                if task.riven_rank == "Unranked":
                    output_riven = "empty_riven_unranked.png"
            
            # Get Prefix and Unit
            get_prefix_and_unit(riven_stat_details)
    
            # Set Grade
            set_grade_new(riven_stat_details, task.weapon_type, weapon_dispo, task.riven_rank)

            # Damage to Faction value correction - percentage_to_decimal
            for i in range(riven_stat_details.StatCount):
                percentage_to_decimal(riven_stat_details, i)

            # print(f"All value : {riven_stat_details.Value}\nAll Min : {riven_stat_details.Min}\nAll Max : {riven_stat_details.Max}")
            # return
            # Create image grading
            # global output_path
            
            # Check if out if range
            out_range, out_range_faction = check_out_range(riven_stat_details)
            # print("!!!!!!!!!!!!!!!!!!!")
            # print(f"weapon_name BEFORE GET BASE NAME : {weapon_name}")
            # print("!!!!!!!!!!!!!!!!!!!")
            base_name = get_base_weapon_name(weapon_name)
            # print("!!!!!!!!!!!!!!!!!!!")
            # print(f"bese_name : {weapon_name}")
            # print("!!!!!!!!!!!!!!!!!!!")
            variants = get_available_variants(file_path, base_name)
            # print("!!!!!!!!!!!!!!!!!!!")
            # print(f"variant available : {variants}")
            # print("!!!!!!!!!!!!!!!!!!!")
            # if out_range == True and len(variants) > 1:
                # add_text_2 = "▶ Please use the dropdown below to select the correct variant.\n▶ Check [#important-info](https://discord.com/channels/1350251436977557534/1350258178998276147) to learn how to identify a Riven’s variant.\n"
            # else:
                # add_text_2 = ""
            # print(f"Variant RANGE : {len(variants)} ::::: {variants}")    
            # print(f"MIN : {riven_stat_details.Min}")
            # print(f"MAX : {riven_stat_details.Max}")
            # print(f"Stat Count : {riven_stat_details.StatCount}")
            
            if out_range == True:
                if len(variants) > 1:
                    add_text_2 = "▶ Please use the dropdown below to select the correct variant.\n▶ Check [#important-info](https://discord.com/channels/1350251436977557534/1350258178998276147/1398554937776013425) to learn how to identify a Riven’s variant.\n"
                else:
                    add_text_2 = ""
                title_text = "GRADING FAILED ❌"
                
                if task.ocr_engine == "OCR Space":
                    description_text = f"{task.interaction.user.mention}\n{add_text_2}▶ If any stats are missing, please upload a clearer image with a better flat angle.\n▶ If the stat value is far from the min-max range, regrade and manually set the Riven rank. [how to?](https://discord.com/channels/1350251436977557534/1351557739066691584/1400775911590334515)\n▶ If the Riven image is sourced from the **riven.market** or **warframe.market** website, be aware that some Rivens may display incorrect or outdated stats due to older uploads or errors made by the uploader."
                else:
                    description_text = f"{task.interaction.user.mention}\n{add_text_2}▶ If the stat value is far from the min-max range, regrade and manually set the Riven rank. [how to?](https://discord.com/channels/1350251436977557534/1351557739066691584/1400775911590334515)\n▶ If it still fails, it may be due to an incorrect input or because the Riven you are referring to is outdated."
                    
            elif out_range == False and out_range_faction == True:
                title_text = "GRADING SUCCESS ✅️"
                description_text = f"{task.interaction.user.mention}\n▶ Damage to Faction is out of range. You may ignore its grade if the Riven image is from the Warframe mobile app.\n\n{add_text}"
            else:
                title_text = "GRADING SUCCESS ✅️"
                description_text = f"{task.interaction.user.mention}\n{add_text}"
            
            if task.ocr_engine == "Random" and task.reroll_counter > 0:
                title_text = "RANDOM GRADING 🔀"
                display_counter_cost = f"**Reroll Counter** : {task.reroll_counter}\n**Kuva Cost** : {task.kuva_cost}\n"
                description_text = f"{task.interaction.user.mention}\n{display_counter_cost}\n{add_text}"
            elif task.ocr_engine == "Random" and task.reroll_counter == 0:
                title_text = "RANDOM GRADING 🔀"
                description_text = f"{task.interaction.user.mention}\n{add_text}"
            
            embed = discord.Embed(title=title_text, description=description_text, color=discord.Color.purple())
            # Add a footer to the embed
            if task.ocr_engine == "OCR Space": 
                embed.set_footer(text=f"Tips: Use an in-game image and a maxed-rank Riven mod for optimal grading!")
            elif task.ocr_engine == "Manual": 
                embed.set_footer(text=f"Tips: Use a maxed-rank Riven mod for optimal grading!")
            elif task.ocr_engine == "Random": 
                embed.set_footer(text=f"Note: Random grading always results in maxed-rank Riven mods!")
                
            # Make sure value stat for no stat name is 999.9
            for i in range(4):
                if riven_stat_details.StatName[i] == "":
                    if riven_stat_details.Value[i] != 999.9:
                        riven_stat_details.Value[i] = 999.9
            
            # Create grading image
            output_path = await create_grading_image(
                riven_stat_details, 
                weapon_name, 
                weapon_dispo, 
                output_riven,  # Pass the file path directly
                task.platinum,
                task.weapon_variant,
                task.ocr_engine
            )
            # Return the path if this is an edit operation
            if is_edit or is_reroll or new_random:
                return output_path, embed
            
            # Create and send the view with the original message reference
            with open(output_path, 'rb') as f:
                file = discord.File(f)
                message = await task.interaction.followup.send(
                    file=file,
                    embed=embed
                )
                
            # Edit the message to add the view after it's created
            if len(variants) > 1 and task.ocr_engine != "Random":  # More than just the base variant and not random command
                # Create and add the view
                view = RegradeView(
                    original_message=message,
                    original_image_path=output_riven,
                    weapon_name=weapon_name,
                    buff_count=task.buff_count,
                    ocr_engine=task.ocr_engine,
                    riven_rank=task.riven_rank,
                    platinum=task.platinum
                )
                view.current_variant = task.weapon_variant
                view.variant = task.weapon_variant
                view.original_task = task
            
                # Set dropdown defaults
                for option in view.variant_select.options:
                    option.default = (option.value == task.weapon_variant)
            
                await message.edit(view=view)
                
            if task.ocr_engine == "Random":
                view = RerollView(
                    original_message=message,
                    weapon_name=weapon_name,
                    weapon_type=task.weapon_type,
                    weapon_variant=task.weapon_variant,
                    original_user=task.interaction.user,
                    reroll_counter=task.reroll_counter,
                    kuva_cost=task.kuva_cost
                )
                await message.edit(view=view)
                
            print("\n" + "=" * 34)
            print("|         GRADING COMPLETE       |")
            print("=" * 34 + "\n")

        except Exception as e:
            print("\n" + "=" * 34)
            print("|         GRADING ERROR          |")
            print("=" * 34 + "\n")
            print(e)
            traceback.print_exc()
            try:
                await task.interaction.followup.send(f"❌ Error processing Riven: {str(e)}")
            except:
                print("Failed to send error")
            
            # Return None when there's an error in edit mode
            if is_edit:
                return None, None
        
@tree.command(name="crop", description="Auto crop Riven mod.")
async def crop_riven(interaction: discord.Interaction, image: discord.Attachment):
    await interaction.response.defer()

    if not image:
        await interaction.followup.send("Please upload an image.")
        return

    try:
        img_bytes = await image.read()

        # Open the image using PIL
        pil_img = Image.open(BytesIO(img_bytes)).convert("RGB")
        img_array = np.array(pil_img)

        # Run detection
        results = model(img_array, verbose=False, iou=0.6)
        crops = []

        for r in results:
            if not r.boxes:
                continue

            for box in r.boxes:
                cls_id = int(box.cls[0])
                name = model.names[cls_id]

                if name == "riven_mod" and float(box.conf[0]) > 0.5:
                    # Get bounding box and crop
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    width = x2 - x1
                    height = y2 - y1
                    
                    if height < width:
                        continue
                        
                    cropped = pil_img.crop((x1, y1, x2, y2))

                    # Save locally
                    unique_name = f"riven_image_crop_{str(uuid.uuid4())[:8]}.jpg"
                    save_path = f"{unique_name}"
                    # os.makedirs("saved_crops", exist_ok=True)
                    cropped.save(save_path, format="JPEG", quality=95)

                    # Also prepare to send to user
                    image_io = BytesIO()
                    cropped.save(image_io, format="JPEG", quality=95)
                    image_io.seek(0)
                    crops.append(File(fp=image_io, filename=unique_name))

        if crops:
            await interaction.followup.send(f"Detected {len(crops)} Riven mod(s):", files=crops)
        else:
            await interaction.followup.send("No Riven mod found in the image.")

    except Exception as e:
        await interaction.followup.send(f"Error processing image: {e}")

async def weapon_autocomplete(interaction, current: str):
    results = [
        app_commands.Choice(name=w["name"], value=w["name"])
        for w in all_weapon_name if current.lower() in w["name"].lower()
    ]
    return results[:25]  # show up to 25 filtered matches
    
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

@tree.command(name="random", description="Grading a Random Riven Mod")
@app_commands.autocomplete(weapon_name=weapon_autocomplete)
async def random_grading(interaction: discord.Interaction, weapon_name:str = None):
    global file_path
    
    await interaction.response.defer(thinking=True)
    
    try:
        task = await random_reroll(interaction, weapon_name)
        
        await process_grading(task, first_random = True)
        
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Failed to grading random Riven mod. Try again later.\n```{e}```")

@tree.command(name="grading", description="Grading a Riven mod.")
@app_commands.choices(
    riven_rank=[
        app_commands.Choice(name="Maxed", value="Maxed"),
        app_commands.Choice(name="Unranked", value="Unranked"),
    ]
)
async def grading(interaction: discord.Interaction, image: discord.Attachment,riven_rank: str = "Auto", platinum: str = None):
    # Allowed image extensions
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    
    # Get file extension
    file_extension = os.path.splitext(image.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        await interaction.response.send_message(
            "Please upload an image file.",
            ephemeral=True
        )
        return
    
    try:
        await interaction.response.defer(thinking=True)
        
        # Set default values
        weapon_variant = "Normal"
        weapon_type = "Auto"
        # riven_rank = "Auto"
        
        # is_up, status_embed = await check_ocr_space_api()
        # if not is_up:
            # await interaction.followup.send(embed=status_embed)
            # await interaction.channel.send("Please try again later, or use manual grading instead. [(how to?)](https://discord.com/channels/1350251436977557534/1350258178998276147/1410190204551041117)")
            # return
        
        # First try to detect and crop Riven mods from the image
        try:
            img_bytes = await image.read()
            pil_img = Image.open(BytesIO(img_bytes)).convert("RGB")
            img_array = np.array(pil_img)

            # Run detection
            results = model(img_array, verbose=False, iou=0.6) # iou=0.6 : Increases overlap requirement so duplicates/partials get merged into the main detection.
            crops = []

            for r in results:
                if not r.boxes:
                    continue

                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    name = model.names[cls_id]

                    if name == "riven_mod" and float(box.conf[0]) > 0.5:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                        # --- FIX START: Check if crop width is shorter than height ---
                        width = x2 - x1
                        height = y2 - y1

                        # Only process if the height is greater than or equal to the width (i.e., not a landscape orientation)
                        if height >= width:
                            cropped = pil_img.crop((x1, y1, x2, y2))
                            crops.append(cropped)
                        # --- FIX END ---
                        
                        # cropped = pil_img.crop((x1, y1, x2, y2))
                        # crops.append(cropped)
            
            # Only notify if multiple Rivens detected
            if len(crops) > 1:
                await interaction.followup.send(f"🔍 Detected {len(crops)} Riven mods. Processing ...")
            elif not crops:
                crops = [pil_img]
                await interaction.followup.send("⚠️ Auto Riven mod detection failed. Processing entire image...")
                
        except Exception as e:
            print(f"Error in crop detection: {e}")
            crops = [Image.open(BytesIO(await image.read()))]
            await interaction.followup.send("⚠️ Auto Riven mod detection failed. Processing entire image...")

        # Process each cropped Riven mod
        for i, crop in enumerate(crops):
            temp_filename = None
            try:
                # Save crop to temporary file
                temp_filename = f"riven_image_temp_{str(uuid.uuid4())[:8]}.jpg"
                crop.save(temp_filename, "JPEG")
                
                # Create task with file path
                task = GradingTask(
                    interaction=interaction,
                    weapon_variant=weapon_variant,
                    weapon_type=weapon_type,
                    riven_rank=riven_rank,
                    image=temp_filename,  # Pass file path directly
                    platinum=platinum,
                    ocr_engine="OCR Space",
                    buff_count=0
                )
                
                await process_grading(task)
                
            except Exception as e:
                print(f"Error processing crop {i}: {e}")
                try:
                    await interaction.followup.send(f"❌ Failed to process Riven mod #{i+1}")
                except Exception as send_error:
                    print(f"Failed to send error: {send_error}")

    except Exception as e:
        print(f"Error in grading command: {e}")
        try:
            await interaction.followup.send("❌ Failed to process your Riven. Please try again.")
        except Exception as send_error:
            print(f"Failed to send error: {send_error}")

@tree.command(name="m_grading", description="Manual grading for a Riven mod.")
@app_commands.autocomplete(weapon_name=weapon_autocomplete)
@app_commands.choices(
    riven_rank=[
        app_commands.Choice(name="Maxed", value="Maxed"),
        app_commands.Choice(name="Unranked", value="Unranked"),
    ]
)
async def m_grading(
    interaction: discord.Interaction, 
    weapon_name: str,
    buff_1: str,
    buff_2: str,
    buff_3: str = None,
    curse: str = None,
    riven_rank: str = "Auto",
    platinum: str = None
):
    await interaction.response.defer(thinking=True)
    
    try:
        # Manually construct the extracted text from the inputs
        # Add buffs
        temp = fix_stat_name(buff_1)
        if buff_1.replace(" ","") == temp.replace(" ",""):
            await interaction.followup.send("❌ You're using the wrong shortform/alias in buff_1 stat. See the full list [here](https://discord.com/channels/1350251436977557534/1350258178998276147/1410213851164840068).")
            return
        extracted_text = temp
        
        temp = fix_stat_name(buff_2)
        if buff_2.replace(" ","") == temp.replace(" ",""):
            await interaction.followup.send("❌ You're using the wrong shortform/alias in buff_2 stat. See the full list [here](https://discord.com/channels/1350251436977557534/1350258178998276147/1410213851164840068).")
            return
        extracted_text += f" {temp}"
        
        buff_count = 2
        if buff_3:
            temp = fix_stat_name(buff_3)
            if buff_3.replace(" ","") == temp.replace(" ",""):
                await interaction.followup.send("❌ You're using the wrong shortform/alias in buff_3 stat. See the full list [here](https://discord.com/channels/1350251436977557534/1350258178998276147/1410213851164840068).")
                return
            extracted_text += f" {temp}"
            buff_count = 3
        if curse:
            temp = fix_stat_name(curse)
            if curse.replace(" ","") == temp.replace(" ",""):
                await interaction.followup.send("❌ You're using the wrong shortform/alias in curse stat. See the full list [here](https://discord.com/channels/1350251436977557534/1350258178998276147/1410213851164840068).")
                return
            extracted_text += f" {temp}"
        
        extracted_text = f"{weapon_name} {extracted_text}"
        
        # Set default values
        weapon_variant = "Normal"
        weapon_type = "Auto"
        
        # Create a task with the mock image path
        task = GradingTask(
            interaction=interaction,
            weapon_variant=weapon_variant,
            weapon_type=weapon_type,
            riven_rank=riven_rank,
            image="empty_riven_maxed.png",
            platinum=platinum,
            ocr_engine="Manual",
            buff_count = buff_count
        )
        
        # Store the manually created text
        task.raw_extracted_text = extracted_text
        
        # Process the grading
        await process_grading(task)
        
    except Exception as e:
        print(f"Error in manual grading command: {e}")
        traceback.print_exc()
        try:
            await interaction.followup.send("❌ Failed to process your manual Riven input. Please try again.")
        except Exception as send_error:
            print(f"Failed to send error: {send_error}")

# all_weapon_data = load_weapon_data(file_path)
# all_weapon_name = [weapon["name"] for weapon in all_weapon_data["ExportWeapons"]]

# @m_grading.autocomplete("weapon_name")
# async def weapon_autocomplete(interaction, current: str):
    # results = [
        # app_commands.Choice(name=w["name"], value=w["name"])
        # for w in all_weapon_name if current.lower() in w["name"].lower()
    # ]
    # return results[:25]  # show up to 25 filtered matches

@client.event
async def on_ready():
    # Define the path to the bot's script location
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Clean up any images containing "riven_image" in the filename
    for filename in os.listdir(script_dir):
        if "riven_image" in filename and filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            try:
                os.remove(os.path.join(script_dir, filename))
                print(f"Deleted: {filename}")
            except Exception as e:
                print(f"Failed to delete {filename}: {e}")
                break
    
    # Load weapon data on startup
    try:
        await get_weapon_data(file_path, weapon_data_url)
        print("Weapon data loaded successfully on startup.")
        
        # Update the weapon name list for autocomplete
        global all_weapon_name
        all_weapon_data = load_weapon_data(file_path)
        
        # 1. Capture both Name and Category in a temporary list
        raw_weapons = []
        for weapon in all_weapon_data["ExportWeapons"]:
            name = weapon.get("name", "")
            unique_name = weapon.get("uniqueName", "")
            category = weapon.get("productCategory", "HahNoTYPE?") # Default if missing

            # Your existing filter logic
            if "<ARCHWING>" in name:
                continue
            
            exclude_keywords = [
                "PetPart", "Powersuits", "Vehicles", "Items", "NechroTech",
                "OperatorAmplifiers", "ModularMelee01/Balance",
                "ModularMeleeInfested/Handles", "Clip", "Handle", "DrifterPistol"
            ]
            if any(x in unique_name for x in exclude_keywords):
                continue
            
            # Get the base name (e.g., "Braton Prime" -> "Braton")
            base_name = get_base_weapon_name(name)
            raw_weapons.append({"name": base_name, "category": category})

        # 2. Remove duplicates by name while keeping the category
        # Using a dict comprehension to keep only the first instance of each base name
        seen = {}
        for w in raw_weapons:
            if w["name"] not in seen:
                seen[w["name"]] = w["category"]
        
        # Convert back to a list of dictionaries
        all_weapon_name = [{"name": name, "category": cat} for name, cat in seen.items()]
        
        # 3. Manually add special weapons
        all_weapon_name.append({"name": "Vinquibus (melee)", "category": "Melee"})
        
        print(f"Loaded {len(all_weapon_name)} weapon names with categories.")
        
    except Exception as e:
        print(f"Failed to load weapon data on startup: {e}")
        all_weapon_name = []
        
    await tree.sync()
    print(f'Logged in as {client.user}')
# Run the bot
client.run(TOKEN)
