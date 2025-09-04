# Deploy Rivenvale on Your Device
## 🔒 Usage Restriction

- You may clone the Rivenvale repository and deploy it on your device for personal use only.
- Commercial use is strictly prohibited.
- You are permitted to modify the code for personal purposes, but you must not alter the Rivenvale logo or name. The logo is located in the repository file `Rivenvale_logo.png`.
- If you are developing your own bot using Rivenvale’s code as a reference, you are free to create your own unique logo and name to establish your bot’s distinct identity. However, you may not use Rivenvale’s proprietary assets, including but not limited to `bg.png`, `best.pt`, or any other associated files provided in the Rivenvale repository.

## 📥 Cloning the Repository

To get started, clone the repository from GitHub to your local device using the following steps:

1. **Ensure Git is Installed**  
   Make sure you have Git installed. You can download it from [git-scm.com](https://git-scm.com/downloads) or verify by running:
```
git --version
```
2. **Clone the Repository**  
After navigate to the project directory, run the following command in your terminal or command prompt to clone the Rivenvale repository:
```
git clone https://github.com/ExerentPrime/Rivenvale.git
```
3. **Verify Cloned Files**  
Check that the repository contents, including `bot.py` and other asset files, are present:
```
ls
```

## 🔧 Environment Setup

You’ll need a `.env` file to store your **Discord bot token** and **OCR API key**.

1. **Get a Discord Bot Token**
   - Create a Discord application and bot via the [Discord Developer Portal](https://discord.com/developers/applications).  
   - Copy your bot token. 

2. **Get an OCR API Key**
   - Go to [OCR.Space](https://ocr.space/ocrapi/freekey).  
   - Register for a **free key** or purchase a **PRO plan** if you need higher limits.

3. **Create the .env File**
   - Inside your project root, create a file named `.env` and paste Discord bot token and OCR API key. The file should look like this:
```
DISCORD_BOT_TOKEN=AAAa99A99AA9A9Aaa99AAA9A999Aa.aAAaaA.AAAAaAaAAA_aaaaa99999AaAaAaAAaa
OCR_API=K99999999999999
```
## 📋 Requirements

To run the bot, ensure you have the following:

### System Requirements
- **Python**: Version 3.8 or higher (tested on 3.12.3). Download from [python.org](https://www.python.org/downloads/).
- **Operating System**: Windows, macOS, or Linux (with support for image processing libraries like OpenCV).

### Python Dependencies
Install the required Python packages using pip.

- **Installation Command**:
```
pip install aiohttp discord.py Pillow requests pandas python-dotenv ultralytics opencv-python numpy
```

## 🚀 Running the Bot
1. Clone the repository as described above.
2. Install dependencies using the commands provided.
3. Set up your `.env` file with the Discord bot token and OCR API key.
4. Ensure required asset files in the project directory.
5. Run the bot:
```
python bot.py
```
## 🔄 Updating and Maintenance

Rivenvale is updated regularly to align with new Warframe patches. To ensure the bot functions correctly, you must update the code and refresh specific data files as outlined below:

### Updating the Bot
- **Pull Latest Code Changes**  
Ensure you have the latest version of the repository:
```
git pull origin main
```
### Maintaining the Data
- **Refresh Data Files**  
Rivenvale automatically downloads `roll_data.xlsx` and `weapon_data.txt` on its first run. However, these files may become outdated after a Warframe patch. To force a refresh, delete the existing files and restart the bot:
```
rm roll_data.xlsx weapon_data.txt
```
