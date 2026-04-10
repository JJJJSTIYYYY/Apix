# Installing LibreOffice for Document Conversion

This guide explains how to install **LibreOffice** on different operating systems so it can be used for headless document-to-PDF conversion.

LibreOffice is required for converting Office files (DOCX, XLSX, PPTX, etc.) into PDF format.

---

## ✅ Windows

### 1. Download LibreOffice

Go to the official website:

https://www.libreoffice.org/download/download/

Download the **Windows (64-bit)** installer.

---

### 2. Install

1. Run the installer.
2. Choose **Typical Installation**.
3. Complete the setup.

---

### 3. Add LibreOffice to PATH (Recommended)

By default, LibreOffice installs to:

```

C:\Program Files\LibreOffice\program\

```

To allow command-line usage:

1. Open **System Properties**
2. Go to **Environment Variables**
3. Edit the `Path` variable
4. Add:

```

C:\Program Files\LibreOffice\program\

```

Restart your terminal after updating PATH.

---

### 4. Verify Installation

Open **Command Prompt** and run:

```

soffice --version

```

If installed correctly, it will print the version number.

---

## ✅ macOS

### Option 1: Official Installer

1. Download from:
   https://www.libreoffice.org/download/download/
2. Open the `.dmg`
3. Drag LibreOffice into the **Applications** folder

---

### Option 2: Install via Homebrew (Recommended)

If you use Homebrew:

```

brew install --cask libreoffice

```

---

### Verify Installation

Run:

```

/Applications/LibreOffice.app/Contents/MacOS/soffice --version

```

If using Homebrew, `soffice` may already be available in PATH.

---

## ✅ Linux

### Ubuntu / Debian

```

sudo apt update
sudo apt install libreoffice

```

---

### CentOS / RHEL / Fedora

```

sudo dnf install libreoffice

```

or:

```

sudo yum install libreoffice

```

---

### Arch Linux

```

sudo pacman -S libreoffice-fresh

```

---

### Verify Installation

```

soffice --version

```

---

## ✅ Headless Mode Test

To confirm LibreOffice can run in headless conversion mode:

```

soffice --headless --convert-to pdf example.docx

```

If successful, it will generate:

```

example.pdf

```

---

## ⚠ Troubleshooting

### "soffice not found"

- Ensure LibreOffice is installed.
- Make sure the `program` directory is added to your system PATH.
- Restart your terminal after modifying PATH.

### Conversion fails silently

- Make sure the document is not open in another program.
- Check file permissions.
- Ensure sufficient disk space.

---

## 🎯 Final Check

Your system is ready if:

- `soffice --version` works
- `--headless --convert-to pdf` works

Once these succeed, your document conversion pipeline is properly configured.

