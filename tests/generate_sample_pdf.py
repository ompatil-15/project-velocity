from reportlab.pdfgen import canvas
import os


def create_sample_kyc():
    file_path = os.path.abspath("tests/sample_kyc.pdf")
    c = canvas.Canvas(file_path)
    c.drawString(100, 750, "GOVERNMENT OF INDIA")
    c.drawString(100, 700, "INCOME TAX DEPARTMENT")
    c.drawString(100, 650, "Name: John Doe")
    c.drawString(100, 600, "Permanent Account Number Card")
    c.drawString(100, 550, "PAN: ABCDE1234F")
    c.drawString(100, 500, "Aadhaar: 1234 1234 1234")
    c.save()
    print(f"Sample KYC PDF created at: {file_path}")


if __name__ == "__main__":
    create_sample_kyc()
