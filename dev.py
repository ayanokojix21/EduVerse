import subprocess
import sys
import os
import threading
import shutil
import signal
from pathlib import Path

# SOTA: Enable ANSI colors on Windows 10+
if os.name == 'nt':
    from ctypes import windll
    kernel32 = windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

# ANSI Colors for beautiful logs
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(msg, color=Colors.OKBLUE):
    print(f"{color}{Colors.BOLD}>>> {msg}{Colors.ENDC}")

def stream_logs(pipe, prefix, color):
    """Reads lines from a pipe and prints them with a prefix."""
    try:
        for line in iter(pipe.readline, ''):
            if line:
                print(f"{color}{prefix}{Colors.ENDC} {line.strip()}")
    except Exception:
        pass

import platform

def check_dependency(cmd, name, install_instructions):
    if shutil.which(cmd) is None:
        if os.name == 'nt' and shutil.which(f"{cmd}.cmd") is not None:
            return
        print(f"\n{Colors.FAIL}❌ Missing Requirement: {name}{Colors.ENDC}")
        print(f"{Colors.WARNING}Please install {name} to run Native Developer Mode.{Colors.ENDC}")
        
        system = platform.system()
        print(f"\n{Colors.OKBLUE}Installation Commands for {system}:{Colors.ENDC}")
        if system == "Windows":
            print(install_instructions.get("Windows", "Please install manually from their official website."))
        elif system == "Darwin":
            print(install_instructions.get("Mac", "Please install manually from their official website."))
        else:
            print(install_instructions.get("Linux", "Please install manually using your package manager."))
            
        print(f"\n{Colors.HEADER}Tip: If you don't want to install this, use Docker instead!{Colors.ENDC}")
        print(f"Run: {Colors.BOLD}docker-compose up --build{Colors.ENDC}\n")
        sys.exit(1)

def run_setup():
    log("Starting EduVerse Native Setup...", Colors.HEADER)
    
    # 1. Check Prerequisites
    check_dependency("ollama", "Ollama", {
        "Windows": "Download from https://ollama.com/download/windows or run:\nwinget install Ollama.Ollama",
        "Mac": "Download from https://ollama.com/download/mac or run:\nbrew install ollama",
        "Linux": "Run:\ncurl -fsSL https://ollama.com/install.sh | sh"
    })
    
    check_dependency("mongod", "MongoDB", {
        "Windows": "Download the MSI from https://www.mongodb.com/try/download/community or run:\nwinget install MongoDB.Server",
        "Mac": "Run:\nbrew tap mongodb/brew\nbrew install mongodb-community@7.0\nbrew services start mongodb-community@7.0",
        "Linux": "Follow the official docs for your distro: https://www.mongodb.com/docs/manual/administration/install-on-linux/"
    })

    check_dependency("node", "Node.js", {
        "Windows": "Download from https://nodejs.org or run:\nwinget install OpenJS.NodeJS",
        "Mac": "Run:\nbrew install node",
        "Linux": "Run:\nsudo apt install nodejs npm"
    })

    check_dependency("python", "Python", {
        "Windows": "Download from https://www.python.org/downloads/windows/",
        "Mac": "Run:\nbrew install python",
        "Linux": "Run:\nsudo apt install python3 python3-pip"
    })
    
    # 2. Setup Backend
    log("Installing Backend Dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt"], check=True)
    
    # 3. Setup Frontend
    log("Installing Frontend Dependencies...")
    subprocess.run(["npm", "install"], cwd="frontend", check=True, shell=(os.name == 'nt'))
    
    # 4. Pull Gemma 4 Model
    log("Ensuring Gemma 4 E4B is available in Ollama...")
    subprocess.run(["ollama", "pull", "gemma4:e4b"], check=True)

    log("Setup Complete! Launching EduVerse Swarm...", Colors.OKGREEN)

def kill_proc(proc):
    """Robustly kill a process and its children."""
    if os.name == 'nt':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    else:
        proc.terminate()

def start_services():
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
        cwd="backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd="frontend",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=(os.name == 'nt')
    )
    
    log("EduVerse is running!", Colors.HEADER)
    log("Frontend: http://localhost:3000", Colors.OKGREEN)
    log("Backend API: http://localhost:8000", Colors.OKBLUE)
    log("Press Ctrl+C to stop all services.", Colors.WARNING)

    t1 = threading.Thread(target=stream_logs, args=(backend_proc.stdout, "[Backend]", Colors.OKBLUE), daemon=True)
    t2 = threading.Thread(target=stream_logs, args=(frontend_proc.stdout, "[Frontend]", Colors.OKGREEN), daemon=True)
    
    t1.start()
    t2.start()

    try:
        while True:
            if backend_proc.poll() is not None:
                log("Backend stopped unexpectedly.", Colors.FAIL)
                break
            if frontend_proc.poll() is not None:
                log("Frontend stopped unexpectedly.", Colors.FAIL)
                break
            threading.Event().wait(1)
    except KeyboardInterrupt:
        log("\nStopping services...", Colors.WARNING)
    finally:
        kill_proc(backend_proc)
        kill_proc(frontend_proc)
        log("EduVerse stopped.", Colors.FAIL)

if __name__ == "__main__":
    if "--skip-setup" in sys.argv:
        start_services()
    else:
        run_setup()
        start_services()
