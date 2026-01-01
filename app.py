import sys
import torch
import threading
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QComboBox, 
                             QStackedWidget, QFileDialog,QInputDialog, QFrame, QScrollArea,
                             QSizePolicy, QGridLayout,QLineEdit,QCheckBox, QDialog, QStyle, QMessageBox,QSpinBox,QProgressDialog)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal,QTimer
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QImage, QPixmap
from PyQt5 import sip
import cv2
import numpy as np
import datetime
import objectTracking
import threading
import time
import traceback
import os
import json
from pathlib import Path
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
import socket
from auth_manager import AuthManager
import queue


# --- Color Palette & Styles ---
BACKGROUND_COLOR = "#111827"  # Dark background
CARD_COLOR = "#1f2937"        # Slightly lighter card
PRIMARY_COLOR = "#0ea5e9"     # Bright Blue
TEXT_COLOR = "#f3f4f6"        # White-ish
SECONDARY_TEXT = "#9ca3af"    # Grey
DANGER_COLOR = "#ef4444"      # Red
ACTIVE_COLOR = "#EF4444"      # Red
HOVER_COLOR = "#2563EB"       # Darker blue for hover
STYLESHEET = f"""
    
    
    
    QMainWindow {{
        background-color: {BACKGROUND_COLOR};
    }}
    QWidget {{
        color: {TEXT_COLOR};
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
    }}
    QFrame#Card {{
        background-color: {CARD_COLOR};
        border-radius: 12px;
        border: 1px solid #374151;
    }}
    QPushButton {{
        background-color: {CARD_COLOR};
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 8px 16px;
        color: {SECONDARY_TEXT};
    }}
    QPushButton:hover {{
        background-color: #374151;
        color: {TEXT_COLOR};
    }}
    QPushButton#PrimaryButton {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border: none;
        font-weight: bold;
        padding: 12px;
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: #0284c7;
    }}
    QPushButton#DangerButton {{
        background-color: transparent;
        border: 1px solid {DANGER_COLOR};
        color: {DANGER_COLOR};
    }}
    QPushButton#DangerButton:hover {{
        background-color: {DANGER_COLOR};
        color: white;
    }}
    QPushButton#TabButton {{
        background-color: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        color: {SECONDARY_TEXT};
        padding-bottom: 10px;
    }}
    QPushButton#TabButton[active="true"] {{
        color: {PRIMARY_COLOR};
        border-bottom: 2px solid {PRIMARY_COLOR};
    }}
    QComboBox {{
        background-color: {BACKGROUND_COLOR};
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 8px;
        color: {TEXT_COLOR};
    }}
    QComboBox::drop-down {{
        border: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {CARD_COLOR};
        color: {TEXT_COLOR};
        selection-background-color: {PRIMARY_COLOR};
        selection-color: white;
        border: 1px solid #374151;
    }}
    /* --- New Dashboard Styles --- */
    QFrame#HeaderFrame {{
        background-color: {CARD_COLOR};
        border-bottom: 1px solid #374151;
    }}
    QFrame#VideoContainer {{
        background-color: black;
        border: 2px solid #374151;
        border-radius: 12px;
    }}
    QFrame#ControlPanel {{
        background-color: {CARD_COLOR};
        border-top: 1px solid #374151;
        border-radius: 12px;
    }}
    QFrame#ClassPanel {{
        background-color: {CARD_COLOR};
        border: 1px solid #374151;
        border-radius: 8px;
    }}
    QCheckBox {{
        spacing: 8px;
        color: {TEXT_COLOR};
        font-size: 14px;
        padding: 4px;
    }}
    QCheckBox::indicator {{
        width: 20px;
        height: 20px;
        border: 1px solid #4B5563;
        border-radius: 6px;
        background-color: {BACKGROUND_COLOR};
    }}
    QCheckBox::indicator:checked {{
        background-color: {PRIMARY_COLOR};
        border: 1px solid {PRIMARY_COLOR};
        image: url(check_icon.png); 
    }}
    QCheckBox::indicator:hover {{
        border: 1px solid {PRIMARY_COLOR};
    }}
    QLabel#Title {{
        font-size: 24px;
        font-weight: bold;
    }}
    QLabel#Subtitle {{
        color: {SECONDARY_TEXT};
        font-size: 14px;
    }}
    QLabel#SectionTitle {{
        font-size: 16px;
        font-weight: bold;
        color: {PRIMARY_COLOR};
        padding-bottom: 8px;
    }}
"""

class AlertManager:
    
    def __init__(self,log_callback=None):
        # Backend attributes
        self.enabled = False
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = "drive27433@gmail.com"
        self.sender_password = "kfoq pcdx blah ckvt"
        self.recipient_emails = []
        self.log_callback = log_callback
        self.log_panel = None
        # Alert queue for async sending
        self.alert_queue = queue.Queue()
        self.alert_thread = None
        self.running = False
        
        # Throttler (will be set externally or created)
        self.throttler = None
        
        
        print(" AlertManager initialized")
    
    def set_throttler(self, throttler):
        """Set the throttler instance"""
        self.throttler = throttler
        print(" Throttler linked to AlertManager")
    
    def configure(self, smtp_server, smtp_port, sender_email, sender_password, recipient_emails):
        """Configure email settings"""
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.recipient_emails = recipient_emails if isinstance(recipient_emails, list) else [recipient_emails]
        
        print(f" Alert configured: {len(self.recipient_emails)} recipients")
    
    def enable(self, enabled=True):
        """Enable or disable alert system"""
        self.enabled = enabled
        
        if enabled and not self.running:
            self.start_alert_worker()
        elif not enabled and self.running:
            self.stop_alert_worker()
        
        status = "ENABLED" if enabled else "DISABLED"
        self.append_log(f"🔧 Alert system: {status}")
    
    def start_alert_worker(self):
        """Start background thread for sending alerts"""
        if not self.running:
            self.running = True
            self.alert_thread = threading.Thread(target=self._alert_worker, daemon=True)
            self.alert_thread.start()
            print(" Alert worker started")
    
    def append_log(self, message, log_type="INFO"):
        """Add log entry using shared panel"""
        if self.log_panel:
            self.log_panel.append_log(message, log_type)
    
    def stop_alert_worker(self):
        """Stop background alert worker"""
        self.running = False
        if self.alert_thread:
            self.alert_thread.join(timeout=2.0)
        self.append_log("🛑 Alert worker stopped")
    
    def _alert_worker(self):
        """Background worker that processes alert queue"""
        while self.running:
            try:
                alert_data = self.alert_queue.get(timeout=1.0)
                success = self._send_email_alert(alert_data)
                
                if success:
                    print(f" Alert sent: {alert_data}")
                else:
                    print(f"❌ Alert failed: {alert_data}")
                
            except queue.Empty:
                continue
            except Exception as e:
               print(f"❌ Alert worker error: {e}")
    
    def queue_batch_alert(self, batch_violation_data, cropped_image_paths, full_image_path):
        """
        Add batched alert to queue (multiple persons, one email)
        
        Args:
            batch_violation_data: dict with batch info
            cropped_image_paths: list of paths to cropped images
            full_image_path: path to full frame image
        """
        if not self.enabled:
            print("⚠️ Alerts Disabled, Not Queuing")
            return False, "Alerts disabled"
        
        if not self.recipient_emails:
            print("⚠️ No Recipients Configured")
            return False, "No recipients"
        
        # Check throttling (use batch_id instead of individual violations)
        if self.throttler:
            # Create signature from batch data
            should_send, reason = self.throttler.should_send_batch_alert(batch_violation_data)
            
            if not should_send:
               print(f"⏸️ Batch alert throttled: {reason}")
               return False, reason
        else:
            reason = "No throttling"
        
        alert_data = {
            "batch_id": batch_violation_data.get("batch_id", "Unknown"),
            "timestamp": batch_violation_data.get("timestamp"),
            "total_persons": batch_violation_data.get("total_persons", 0),
            "persons": batch_violation_data.get("persons", []),
            "severity": batch_violation_data.get("severity", "MEDIUM"),
            "cropped_images": cropped_image_paths,  # List of paths
            "full_image": full_image_path,
            "alert_reason": reason
        }
        
        self.alert_queue.put(alert_data)
        print(f"📧 Batch alert queued: {alert_data['batch_id']} ({alert_data['total_persons']} persons, {reason})")
        return True, reason

    def _send_email_alert(self, alert_data):
        """Send email alert for batched violations"""
        try:
            msg = MIMEMultipart('related')
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.recipient_emails)
            
            total_persons = alert_data.get('total_persons', 0)
            msg['Subject'] = f"🚨 PPE Violation Alert - {total_persons} Person(s) - {alert_data['severity']}"
            
            html_body = self._create_batch_html_body(alert_data)
            msg.attach(MIMEText(html_body, 'html'))
            
            # Attach cropped images (one per person)
            cropped_paths = alert_data.get('cropped_images', [])
            for idx, crop_path in enumerate(cropped_paths):
                try:
                    with open(crop_path, 'rb') as f:
                        img_data = f.read()
                        img = MIMEImage(img_data, name=f'person_{idx+1}_crop.jpg')
                        img.add_header('Content-ID', f'<person_{idx+1}_crop>')
                        msg.attach(img)
                except Exception as e:
                   print(f"⚠️ Could not attach crop {idx+1}: {e}")
            
            # Attach full frame image
            try:
                with open(alert_data['full_image'], 'rb') as f:
                    img_data = f.read()
                    img = MIMEImage(img_data, name='full_scene.jpg')
                    img.add_header('Content-ID', '<full_image>')
                    msg.attach(img)
            except Exception as e:
                print(f"⚠️ Could not attach full image: {e}")
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            return True
        
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False
    
    def _create_batch_html_body(self, alert_data):
        """Create modern, professional HTML email body for batched violations"""
        total_persons = alert_data.get('total_persons', 0)
        severity = alert_data.get('severity', 'MEDIUM')
        persons = alert_data.get('persons', [])
        timestamp = alert_data.get('timestamp', datetime.datetime.now().isoformat())
        
        # Parse timestamp for better formatting
        try:
            dt = datetime.datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime("%B %d, %Y at %I:%M %p")
        except:
            formatted_time = timestamp
        
        # Severity styling
        severity_config = {
            "CRITICAL": {
                "color": "#DC2626",
                "bg": "linear-gradient(135deg, #DC2626, #991B1B)",
                "icon": "🔴",
                "label": "CRITICAL"
            },
            "HIGH": {
                "color": "#EF4444",
                "bg": "linear-gradient(135deg, #EF4444, #DC2626)",
                "icon": "🔴",
                "label": "HIGH"
            },
            "MEDIUM": {
                "color": "#F59E0B",
                "bg": "linear-gradient(135deg, #F59E0B, #D97706)",
                "icon": "🟡",
                "label": "MEDIUM"
            },
            "LOW": {
                "color": "#FCD34D",
                "bg": "linear-gradient(135deg, #FCD34D, #F59E0B)",
                "icon": "🟡",
                "label": "LOW"
            }
        }
        
        config = severity_config.get(severity, severity_config["MEDIUM"])
        
        # Build person cards HTML
        persons_html = ""
        for idx, person in enumerate(persons):
            missing_items = person.get('missing_items', [])
            confidence = person.get('confidence', 0) * 100
            
            # Create missing items badges
            missing_badges = ""
            for item in missing_items:
                missing_badges += f"""
                    <span style="
                        display:inline-block;
                        padding:6px 12px;
                        background-color:#FEE2E2;
                        color:#991B1B;
                        border-radius:6px;
                        font-size:12px;
                        font-weight:600;
                        margin:4px 4px 4px 0;
                    ">
                        ❌ {item}
                    </span>
                """
            
            persons_html += f"""
            <div style="
                background:linear-gradient(135deg, #ffffff, #f9fafb);
                border-radius:16px;
                padding:24px;
                margin-bottom:20px;
                box-shadow:0 4px 15px rgba(0,0,0,0.08);
                border:2px solid {config['color']};
            ">
                <!-- Person Header -->
                <div style="
                    display:flex;
                    align-items:center;
                    justify-content:space-between;
                    margin-bottom:16px;
                    padding-bottom:12px;
                    border-bottom:2px solid #e5e7eb;
                ">
                    <div style="display:flex; align-items:center;">
                        <div style="
                            width:48px;
                            height:48px;
                            background:{config['bg']};
                            border-radius:12px;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            font-size:24px;
                            margin-right:12px;
                        ">
                            👤
                        </div>
                        <div>
                            <h3 style="
                                margin:0;
                                font-size:18px;
                                font-weight:700;
                                color:#111827;
                            ">
                                Person {idx + 1}
                            </h3>
                            <p style="
                                margin:4px 0 0;
                                font-size:13px;
                                color:#6b7280;
                            ">
                                Confidence: {confidence:.1f}%
                            </p>
                        </div>
                    </div>
                    
                    <span style="
                        padding:6px 14px;
                        background-color:{config['color']};
                        color:white;
                        border-radius:20px;
                        font-size:12px;
                        font-weight:700;
                        text-transform:uppercase;
                        letter-spacing:0.5px;
                    ">
                        {config['icon']} {config['label']}
                    </span>
                </div>
                
                <!-- Missing Items -->
                <div style="margin-bottom:16px;">
                    <h4 style="
                        margin:0 0 10px;
                        font-size:14px;
                        font-weight:600;
                        color:#374151;
                        text-transform:uppercase;
                        letter-spacing:0.5px;
                    ">
                        ⚠️ Missing PPE Items
                    </h4>
                    <div>
                        {missing_badges}
                    </div>
                </div>
                
                <!-- Person Image -->
                <div style="
                    border-radius:12px;
                    overflow:hidden;
                    border:3px solid {config['color']};
                    box-shadow:0 4px 12px rgba(0,0,0,0.1);
                ">
                    <img src="cid:person_{idx + 1}_crop" style="
                        width:100%;
                        height:auto;
                        display:block;
                    ">
                </div>
            </div>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta name="color-scheme" content="light">
            <meta name="supported-color-schemes" content="light">
            <title>PPE Violation Alert</title>
        </head>
        
        <body style="
            margin:0;
            padding:0;
            background-color:#f3f4f6;
            font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        ">
        
        <!-- Main Container -->
        <div style="
            max-width:750px;
            margin:0 auto;
            padding:20px;
        ">
            
            <!-- Header Card -->
            <div style="
                background:{config['bg']};
                border-radius:20px 20px 0 0;
                padding:40px 30px;
                text-align:center;
                box-shadow:0 10px 40px rgba(0,0,0,0.15);
            ">
                <!-- Logo/Icon -->
                <div style="
                    width:80px;
                    height:80px;
                    background:rgba(255,255,255,0.2);
                    border-radius:20px;
                    margin:0 auto 20px;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    font-size:40px;
                    backdrop-filter:blur(10px);
                ">
                    🚨
                </div>
                
                <h1 style="
                    margin:0 0 12px;
                    font-size:32px;
                    font-weight:800;
                    color:#ffffff;
                    letter-spacing:-0.5px;
                    line-height:1.2;
                ">
                    PPE Violation Detected
                </h1>
                
                <p style="
                    margin:0;
                    font-size:16px;
                    color:rgba(255,255,255,0.9);
                    font-weight:500;
                ">
                    Multiple safety violations require immediate attention
                </p>
                
                <!-- Stats Badges -->
                <div style="
                    display:flex;
                    justify-content:center;
                    gap:12px;
                    margin-top:24px;
                    flex-wrap:wrap;
                ">
                    <div style="
                        background:rgba(255,255,255,0.25);
                        padding:10px 20px;
                        border-radius:12px;
                        backdrop-filter:blur(10px);
                    ">
                        <div style="
                            font-size:24px;
                            font-weight:800;
                            color:#ffffff;
                            line-height:1;
                        ">
                            {total_persons}
                        </div>
                        <div style="
                            font-size:11px;
                            color:rgba(255,255,255,0.9);
                            margin-top:4px;
                            font-weight:600;
                            text-transform:uppercase;
                            letter-spacing:0.5px;
                        ">
                            Person(s)
                        </div>
                    </div>
                    
                    <div style="
                        background:rgba(255,255,255,0.25);
                        padding:10px 20px;
                        border-radius:12px;
                        backdrop-filter:blur(10px);
                    ">
                        <div style="
                            font-size:24px;
                            font-weight:800;
                            color:#ffffff;
                            line-height:1;
                        ">
                            {config['icon']}
                        </div>
                        <div style="
                            font-size:11px;
                            color:rgba(255,255,255,0.9);
                            margin-top:4px;
                            font-weight:600;
                            text-transform:uppercase;
                            letter-spacing:0.5px;
                        ">
                            {config['label']}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Content Card -->
            <div style="
                background:#ffffff;
                padding:40px 30px;
                box-shadow:0 10px 40px rgba(0,0,0,0.15);
            ">
                
                <!-- Alert Info Box -->
                <div style="
                    background:linear-gradient(135deg, #EFF6FF, #DBEAFE);
                    border-left:4px solid #0ea5e9;
                    border-radius:12px;
                    padding:20px;
                    margin-bottom:32px;
                ">
                    <table style="width:100%; border-collapse:collapse;">
                        <tr>
                            <td style="padding:8px 0; font-size:13px; color:#6b7280; font-weight:600; width:120px;">
                                🆔 Batch ID
                            </td>
                            <td style="padding:8px 0; font-size:13px; color:#111827; font-weight:500;">
                                <code style="
                                    background:#f3f4f6;
                                    padding:4px 8px;
                                    border-radius:6px;
                                    font-family:'Courier New', monospace;
                                    font-size:12px;
                                ">
                                    {alert_data['batch_id'][:16]}
                                </code>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:8px 0; font-size:13px; color:#6b7280; font-weight:600;">
                                🕐 Time
                            </td>
                            <td style="padding:8px 0; font-size:13px; color:#111827; font-weight:500;">
                                {formatted_time}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:8px 0; font-size:13px; color:#6b7280; font-weight:600;">
                                📊 Severity
                            </td>
                            <td style="padding:8px 0;">
                                <span style="
                                    display:inline-block;
                                    padding:4px 12px;
                                    background-color:{config['color']};
                                    color:white;
                                    border-radius:6px;
                                    font-size:12px;
                                    font-weight:700;
                                ">
                                    {config['icon']} {config['label']}
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:8px 0; font-size:13px; color:#6b7280; font-weight:600;">
                                👥 Total
                            </td>
                            <td style="padding:8px 0; font-size:13px; color:#111827; font-weight:700;">
                                {total_persons} Person(s)
                            </td>
                        </tr>
                    </table>
                </div>
                
                <!-- Section Header -->
                <div style="
                    border-bottom:3px solid #e5e7eb;
                    padding-bottom:12px;
                    margin-bottom:24px;
                ">
                    <h2 style="
                        margin:0;
                        font-size:22px;
                        font-weight:700;
                        color:#111827;
                        display:flex;
                        align-items:center;
                    ">
                        <span style="
                            display:inline-block;
                            width:6px;
                            height:24px;
                            background:{config['bg']};
                            border-radius:3px;
                            margin-right:12px;
                        "></span>
                        Individual Violations
                    </h2>
                </div>
                
                <!-- Person Cards -->
                {persons_html}
                
                <!-- Full Scene Section -->
                <div style="
                    border-bottom:3px solid #e5e7eb;
                    padding-bottom:12px;
                    margin:40px 0 24px;
                ">
                    <h2 style="
                        margin:0;
                        font-size:22px;
                        font-weight:700;
                        color:#111827;
                        display:flex;
                        align-items:center;
                    ">
                        <span style="
                            display:inline-block;
                            width:6px;
                            height:24px;
                            background:{config['bg']};
                            border-radius:3px;
                            margin-right:12px;
                        "></span>
                        Complete Scene
                    </h2>
                </div>
                
                <div style="
                    border-radius:16px;
                    overflow:hidden;
                    border:3px solid {config['color']};
                    box-shadow:0 8px 24px rgba(0,0,0,0.12);
                ">
                    <img src="cid:full_image" style="
                        width:100%;
                        height:auto;
                        display:block;
                    ">
                </div>
                
                <!-- Action Required Box -->
                <div style="
                    background:linear-gradient(135deg, #FEF3C7, #FDE68A);
                    border-left:4px solid #F59E0B;
                    border-radius:12px;
                    padding:24px;
                    margin-top:32px;
                    text-align:center;
                ">
                    <div style="
                        font-size:36px;
                        margin-bottom:12px;
                    ">
                        ⚠️
                    </div>
                    <h3 style="
                        margin:0 0 8px;
                        font-size:20px;
                        font-weight:700;
                        color:#92400E;
                    ">
                        Immediate Action Required
                    </h3>
                    <p style="
                        margin:0;
                        font-size:14px;
                        color:#78350F;
                        line-height:1.6;
                    ">
                        Multiple workers detected without proper PPE equipment.<br>
                        Please address this safety violation immediately.
                    </p>
                </div>
                
            </div>
            
            <!-- Footer -->
            <div style="
                background:#1f2937;
                border-radius:0 0 20px 20px;
                padding:30px;
                text-align:center;
                box-shadow:0 10px 40px rgba(0,0,0,0.15);
            ">
                <div style="
                    width:48px;
                    height:48px;
                    background:linear-gradient(135deg, #0ea5e9, #0284c7);
                    border-radius:12px;
                    margin:0 auto 16px;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    font-size:24px;
                ">
                    🛡️
                </div>
                
                <h4 style="
                    margin:0 0 8px;
                    font-size:16px;
                    font-weight:700;
                    color:#f3f4f6;
                ">
                    PPE Safety Monitoring System
                </h4>
                
                <p style="
                    margin:0 0 16px;
                    font-size:13px;
                    color:#9ca3af;
                    line-height:1.5;
                ">
                    Automated violation detection and alert system<br>
                    This is an automated message • Do not reply
                </p>
                
                <div style="
                    padding-top:16px;
                    border-top:1px solid #374151;
                ">
                    <p style="
                        margin:0;
                        font-size:11px;
                        color:#6b7280;
                    ">
                        © 2025 PPE Safety Monitor • All rights reserved
                    </p>
                </div>
            </div>
            
        </div>
        
        </body>
        </html>
        """
        
        return html

    def test_connection(self):
        """Test email connection without starttls timeout"""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.set_debuglevel(0)
                server.starttls()
                server.login(self.sender_email, self.sender_password)
            return True, "Connection successful"
        except smtplib.SMTPAuthenticationError:
            return False, "Authentication failed (check password)"
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {str(e)}"
        except socket.timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def send_test_alert(self):
        """Send test alert without starttls timeout"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.recipient_emails)
            msg['Subject'] = "🧪 Test Alert - PPE Monitoring System"
            
            body = """
            This is a test alert from the PPE Safety Monitoring System.
            
            If you received this email, the alert system is working correctly.
            
            System Status: OK
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.set_debuglevel(0)
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            return True, "Test alert sent"
        except Exception as e:
            return False, str(e)
    
    def get_throttle_stats(self):
        """Get throttling statistics"""
        if self.throttler:
            return self.throttler.get_all_stats()
        return []
    
    def reset_throttle(self):
        """Reset all throttling"""
        if self.throttler:
            self.throttler.reset_all()
    
    def set_throttle_interval(self, minutes):
        """Update throttle interval"""
        if self.throttler:
            self.throttler.set_interval(minutes)
    
    # DIALOG FUNCTIONALITY

    def show_config_dialog(self, parent=None):
        """
         Show configuration dialog
        Returns True if config was saved, False if cancelled
        """

        dialog = QDialog(parent)
        dialog.setWindowTitle("Configure Email Alerts")
        dialog.setFixedWidth(500)

        # Apply stylesheet
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {CARD_COLOR};
                border: 1px solid #374151;
                border-radius: 8px;
            }}
            QLabel {{
                color: {TEXT_COLOR};
                font-size: 14px;
            }}
            QLineEdit {{
                background-color: {BACKGROUND_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid #374151;
                padding: 8px;
                border-radius: 4px;
            }}
            QLineEdit:focus {{
                border: 1px solid {PRIMARY_COLOR};
            }}
            QComboBox {{
                background-color: {BACKGROUND_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid #374151;
                padding: 8px;
                border-radius: 4px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {CARD_COLOR};
                color: {TEXT_COLOR};
                selection-background-color: {PRIMARY_COLOR};
                selection-color: white;
                border: 1px solid #374151;
            }}
            QPushButton {{
                background-color: {PRIMARY_COLOR};
                color: white;
                border: none;
                padding: 10px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #0284c7;
            }}
            QPushButton:disabled {{
                background-color: #374151;
                color: #6b7280;
            }}
            QPushButton#Secondary {{
                background-color: transparent;
                border: 1px solid #374151;
                color: {SECONDARY_TEXT};
            }}
            QPushButton#Secondary:hover {{
                background-color: #374151;
                color: {TEXT_COLOR};
            }}
            QProgressDialog {{
                background-color: {CARD_COLOR};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("📧 Email Alert Configuration")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        layout.addWidget(title)

        # SMTP Server
        layout.addWidget(QLabel("SMTP Server:"))
        smtp_server_input = QLineEdit()
        smtp_server_input.setText(self.smtp_server)
        smtp_server_input.setPlaceholderText("smtp.gmail.com")
        layout.addWidget(smtp_server_input)

        # SMTP Port
        layout.addWidget(QLabel("SMTP Port:"))
        smtp_port_input = QLineEdit()
        smtp_port_input.setText(str(self.smtp_port))
        smtp_port_input.setPlaceholderText("587")
        layout.addWidget(smtp_port_input)

        # Sender Email
        layout.addWidget(QLabel("Sender Email:"))
        sender_email_input = QLineEdit()
        sender_email_input.setText(self.sender_email)
        sender_email_input.setPlaceholderText("your.email@gmail.com")
        layout.addWidget(sender_email_input)

        # Sender Password
        layout.addWidget(QLabel("App Password:"))
        sender_password_input = QLineEdit()
        sender_password_input.setEchoMode(QLineEdit.Password)
        sender_password_input.setText(self.sender_password)
        sender_password_input.setPlaceholderText("Your app password")
        layout.addWidget(sender_password_input)

        # Help text
        help_text = QLabel(
            "⚠️ For Gmail: Use App Password, not regular password.\n"
            "Generate at: Google Account → Security → 2-Step → App passwords"
        )
        help_text.setStyleSheet(
            f"color: {SECONDARY_TEXT}; font-size: 11px; padding: 10px; "
            "background-color: rgba(255,255,255,0.05); border-radius: 4px;"
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        # Recipients
        layout.addWidget(QLabel("Recipients (comma-separated):"))
        recipients_input = QLineEdit()
        recipients_input.setText(', '.join(self.recipient_emails))
        recipients_input.setPlaceholderText("email1@example.com, email2@example.com")
        layout.addWidget(recipients_input)

        # Test Connection Button
        def test_connection_clicked():
            # Create progress dialog
            progress = QProgressDialog("Testing connection...", None, 0, 0, dialog)
            progress.setWindowModality(Qt.WindowModal) # type: ignore
            progress.setWindowTitle("Please Wait")
            progress.setCancelButton(None)
            progress.setMinimumDuration(0)
            progress.show()

            # Disable button during test
            test_btn.setEnabled(False)
            QApplication.processEvents()

            try:
                # Apply temp config
                temp_recipients = [email.strip() for email in recipients_input.text().split(',') if email.strip()]
                self.configure(
                    smtp_server=smtp_server_input.text(),
                    smtp_port=int(smtp_port_input.text() or 587),
                    sender_email=sender_email_input.text(),
                    sender_password=sender_password_input.text(),
                    recipient_emails=temp_recipients
                )

                # Test
                success, message = self.test_connection()

                # Close progress dialog
                progress.close()

                # Show result
                if success:
                    QMessageBox.information(dialog, "Success", f" {message}")
                else:
                    QMessageBox.warning(dialog, "Failed", f"❌ {message}")
            finally:
                # Re-enable button
                test_btn.setEnabled(True)
                progress.close()

        test_btn = QPushButton("🔍 Test Connection")
        test_btn.setCursor(Qt.PointingHandCursor)
        test_btn.clicked.connect(test_connection_clicked)
        layout.addWidget(test_btn)

        # Send Test Alert Button
        def send_test_clicked():
            # Create progress dialog
            progress = QProgressDialog("Sending test alert...", None, 0, 0, dialog)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("Please Wait")
            progress.setCancelButton(None)
            progress.setMinimumDuration(0)
            progress.show()

            # Disable button during send
            test_alert_btn.setEnabled(False)
            QApplication.processEvents()

            try:
                # Apply temp config
                temp_recipients = [email.strip() for email in recipients_input.text().split(',') if email.strip()]
                self.configure(
                    smtp_server=smtp_server_input.text(),
                    smtp_port=int(smtp_port_input.text() or 587),
                    sender_email=sender_email_input.text(),
                    sender_password=sender_password_input.text(),
                    recipient_emails=temp_recipients
                )

                # Send test
                success, message = self.send_test_alert()

                # Close progress dialog
                progress.close()

                # Show result
                if success:
                    QMessageBox.information(dialog, "Success", " Test alert sent! Check your inbox.")
                else:
                    QMessageBox.warning(dialog, "Failed", f"❌ Failed to send:\n\n{message}")
            finally:
                # Re-enable button
                test_alert_btn.setEnabled(True)
                progress.close()

        test_alert_btn = QPushButton("📧 Send Test Alert")
        test_alert_btn.setCursor(Qt.PointingHandCursor)
        test_alert_btn.clicked.connect(send_test_clicked)
        layout.addWidget(test_alert_btn)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("Secondary")  # Apply secondary button style
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        def save_clicked():
            # Save config
            temp_recipients = [email.strip() for email in recipients_input.text().split(',') if email.strip()]
            self.configure(
                smtp_server=smtp_server_input.text(),
                smtp_port=int(smtp_port_input.text() or 587),
                sender_email=sender_email_input.text(),
                sender_password=sender_password_input.text(),
                recipient_emails=temp_recipients
            )
            dialog.accept()

        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(save_clicked)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        # Show dialog
        result = dialog.exec_()
        return result == QDialog.Accepted

class AlertThrottler:
    """
    AlertThrottler backend + ThrottleSettingsDialog UI
    Prevents alert spam by enforcing time-based throttling
    """
    
    def __init__(self, throttle_interval_minutes=15):
        self.throttle_interval = datetime.timedelta(minutes=throttle_interval_minutes)
        self.last_alert_times = {}
        self.alert_counts = {}
        self.log_panel = None
        
        print(f" AlertThrottler initialized (interval: {throttle_interval_minutes} min)")
    
    def set_interval(self, minutes):
        """Update throttle interval"""
        self.throttle_interval = datetime.timedelta(minutes=minutes)
        self.append_log(f"⏱️ Throttle interval set to: {minutes} minutes")
    
    def should_send_alert(self, violation_data):
        """Check if alert should be sent based on throttling rules"""
        signature = self._create_signature(violation_data)
        current_time = datetime.datetime.now()
        
        if signature in self.last_alert_times:
            last_alert_time = self.last_alert_times[signature]
            time_since_last = current_time - last_alert_time
            
            if time_since_last < self.throttle_interval:
                remaining = self.throttle_interval - time_since_last
                minutes_remaining = int(remaining.total_seconds() / 60)
                return False, f"Throttled ({minutes_remaining} min remaining)"
            else:
                self.last_alert_times[signature] = current_time
                self.alert_counts[signature] = self.alert_counts.get(signature, 0) + 1
                return True, f"Resend (#{self.alert_counts[signature]})"
        else:
            self.last_alert_times[signature] = current_time
            self.alert_counts[signature] = 1
            return True, "First alert"
    
    def _create_signature(self, violation_data):
        """Create unique signature for violation type"""
        missing_items = sorted(violation_data.get("missing_items", []))
        return "_".join(missing_items)
    
    def get_alert_stats(self, violation_data):
        """Get statistics for specific violation type"""
        signature = self._create_signature(violation_data)
        
        if signature not in self.last_alert_times:
            return {
                "total_alerts": 0,
                "last_alert": None,
                "next_alert_available": "Now"
            }
        
        last_time = self.last_alert_times[signature]
        count = self.alert_counts.get(signature, 0)
        current_time = datetime.datetime.now()
        time_since_last = current_time - last_time
        
        if time_since_last < self.throttle_interval:
            remaining = self.throttle_interval - time_since_last
            minutes_remaining = int(remaining.total_seconds() / 60)
            next_available = f"In {minutes_remaining} minutes"
        else:
            next_available = "Now"
        
        return {
            "total_alerts": count,
            "last_alert": last_time.strftime("%H:%M:%S"),
            "next_alert_available": next_available
        }
    
    def append_log(self, message, log_type="INFO"):
        """Add log entry using shared panel"""
        if self.log_panel:
            self.log_panel.append_log(message, log_type)

    def reset_signature(self, violation_data):
        """Reset throttling for specific violation type"""
        signature = self._create_signature(violation_data)
        
        if signature in self.last_alert_times:
            del self.last_alert_times[signature]
        if signature in self.alert_counts:
            del self.alert_counts[signature]
        
        print(f"🔄 Throttle reset for: {signature}")
    
    def reset_all(self):
        """Reset all throttling"""
        self.last_alert_times.clear()
        self.alert_counts.clear()
        self.append_log("🔄 All throttling reset")
    
    def get_all_stats(self):
        """Get statistics for all tracked violations"""
        stats = []
        
        for signature, last_time in self.last_alert_times.items():
            count = self.alert_counts.get(signature, 0)
            current_time = datetime.datetime.now()
            time_since_last = current_time - last_time
            
            if time_since_last < self.throttle_interval:
                remaining = self.throttle_interval - time_since_last
                minutes_remaining = int(remaining.total_seconds() / 60)
                status = f"Throttled ({minutes_remaining} min)"
            else:
                status = "Ready"
            
            stats.append({
                "violation_type": signature.replace("_", ", "),
                "alert_count": count,
                "last_alert": last_time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": status
            })
        
        return stats
    
    def should_send_batch_alert(self, batch_data):
        """Check if batch alert should be sent based on throttling rules"""
        # Use timestamp-based signature for batches (not violation type)
        # This allows multiple batches within throttle window
        timestamp = batch_data.get("timestamp", datetime.datetime.now().isoformat())
        signature = f"batch_{timestamp[:16]}"  # Group by minute
        
        current_time = datetime.datetime.now()
        
        if signature in self.last_alert_times:
            last_alert_time = self.last_alert_times[signature]
            time_since_last = current_time - last_alert_time
            
            if time_since_last < self.throttle_interval:
                remaining = self.throttle_interval - time_since_last
                minutes_remaining = int(remaining.total_seconds() / 60)
                return False, f"Throttled ({minutes_remaining} min remaining)"
            else:
                self.last_alert_times[signature] = current_time
                self.alert_counts[signature] = self.alert_counts.get(signature, 0) + 1
                return True, f"Resend (#{self.alert_counts[signature]})"
        else:
            self.last_alert_times[signature] = current_time
            self.alert_counts[signature] = 1
            return True, "First alert"

    # DIALOG FUNCTIONALITY
    
    def show_settings_dialog(self, parent=None):
        """
        Show throttle settings dialog
        Returns True if settings were saved, False if cancelled
        """
        dialog = QDialog(parent)
        dialog.setWindowTitle("Alert Throttling Settings")
        dialog.setFixedWidth(500)

        # Apply stylesheet
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {CARD_COLOR};
                border: 1px solid #374151;
                border-radius: 8px;
            }}
            QLabel {{
                color: {TEXT_COLOR};
                font-size: 14px;
            }}
            QLineEdit {{
                background-color: {BACKGROUND_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid #374151;
                padding: 8px;
                border-radius: 4px;
            }}
            QLineEdit:focus {{
                border: 1px solid {PRIMARY_COLOR};
            }}
            QSpinBox {{
                background-color: rgba(255,255,255,0.05);
                border: 1px solid #374151;
                border-radius: 4px;
                color: white;
                padding: 8px;
            }}
            QSpinBox:focus {{
                border: 1px solid {PRIMARY_COLOR};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: transparent;
                border: none;
                width: 20px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {PRIMARY_COLOR};
                
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {BACKGROUND_COLOR};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #374151;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #4b5563;
            }}
            QFrame {{
                background-color: rgba(255,255,255,0.05);
                border: 1px solid #374151;
                border-radius: 4px;
            }}
            QPushButton {{
                background-color: {PRIMARY_COLOR};
                color: white;
                border: none;
                padding: 10px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #0284c7;
            }}
            QPushButton:disabled {{
                background-color: #374151;
                color: #6b7280;
            }}
            QPushButton#Secondary {{
                background-color: transparent;
                border: 1px solid #374151;
                color: {SECONDARY_TEXT};
            }}
            QPushButton#Secondary:hover {{
                background-color: #374151;
                color: {TEXT_COLOR};
            }}
            QMessageBox {{
                background-color: {CARD_COLOR};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("⏱️ Alert Throttling Configuration")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Throttling prevents alert spam by enforcing a minimum time interval "
            "between alerts for the same violation type."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {SECONDARY_TEXT}; padding: 10px; "
            "background-color: rgba(255,255,255,0.05); border-radius: 4px;"
        )
        layout.addWidget(desc)

        # Interval setting
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Throttle Interval"))

        interval_spinbox = QSpinBox()
        interval_spinbox.setRange(1, 120)
        interval_spinbox.setValue(int(self.throttle_interval.total_seconds() / 60))
        interval_spinbox.setSuffix(" minutes")
        interval_layout.addWidget(interval_spinbox)
        interval_layout.addStretch()

        layout.addLayout(interval_layout)

        # Example explanation
        example = QLabel(
            "📖 Example:\n"
            "• 10:00 - Alert sent for 'Missing hard hat'\n"
            "• 10:05 - Same violation → Alert BLOCKED (throttled)\n"
            "• 10:15 - Same violation → Alert SENT (interval passed)"
        )
        example.setWordWrap(True)
        example.setStyleSheet(
            f"color: {TEXT_COLOR}; padding: 15px; "
            "background-color: rgba(14, 165, 233, 0.1); "
            "border-left: 3px solid #0ea5e9; border-radius: 4px; font-size: 12px;"
        )
        layout.addWidget(example)

        # Statistics
        stats_label = QLabel("Current Throttle Status:")
        stats_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(stats_label)

        # Stats scroll area
        stats_scroll = QScrollArea()
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setMaximumHeight(200)

        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)

        throttle_stats = self.get_all_stats()

        if throttle_stats:
            for stat in throttle_stats:
                stat_frame = QFrame()
                stat_frame.setStyleSheet(
                    "background-color: rgba(255,0,255,0.05); "
                    "border: 1px solid #374151; border-radius: 4px; padding: 10px;"
                )

                stat_layout_inner = QVBoxLayout(stat_frame)
                stat_layout_inner.setSpacing(5)

                type_label = QLabel(f"🔸 {stat['violation_type']}")
                type_label.setStyleSheet("font-weight: bold; color: white;")
                stat_layout_inner.addWidget(type_label)

                info_label = QLabel(
                    f"Alerts sent: {stat['alert_count']} | "
                    f"Last: {stat['last_alert']} | "
                    f"Status: {stat['status']}"
                )
                info_label.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 11px;")
                stat_layout_inner.addWidget(info_label)

                stats_layout.addWidget(stat_frame)
        else:
            no_stats = QLabel("No throttling data yet")
            no_stats.setStyleSheet(
                f"color: {SECONDARY_TEXT}; font-style: italic; padding: 20px;"
            )
            no_stats.setAlignment(Qt.AlignCenter)
            stats_layout.addWidget(no_stats)

        stats_scroll.setWidget(stats_widget)
        layout.addWidget(stats_scroll)

        # Reset button
        def reset_clicked():
            reply = QMessageBox.question(
                dialog,
                "Reset Throttling",
                "This will reset all throttle timers. Alerts will be sent immediately for all violation types.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.reset_all()
                QMessageBox.information(dialog, "Success", " Throttling reset!")
                dialog.accept()

        reset_btn = QPushButton("🔄 Reset All Throttling")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(reset_clicked)
        layout.addWidget(reset_btn)

        # Dialog buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("Secondary")  # Apply secondary button style
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        def save_clicked():
            interval_minutes = interval_spinbox.value()
            self.set_interval(interval_minutes)
            QMessageBox.information(
                dialog,
                "Success",
                f" Throttle interval set to {interval_minutes} minutes"
            )
            dialog.accept()

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(save_clicked)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        # Show dialog
        result = dialog.exec_()
        return result == QDialog.Accepted

class ClassSelectionPanel(QWidget):
    """
    ClassSelectionPanel UI + SelectedClassesHandler logic
    Shared reusable component for class selection with automatic backend sync
    """
    
    def __init__(self, title="Detection Classes", subtitle="Select objects to track", backend_detector=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.checkboxes = {}
        self.backend_detector = backend_detector
        self.prev_state = {}
        self.log_panel = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the class selection panel UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(15)
        
        # Title
        title_label = QLabel(self.title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel(self.subtitle)
        subtitle_label.setStyleSheet(f"color: {SECONDARY_TEXT}; font-size: 12px;")
        layout.addWidget(subtitle_label)
        
        # Scroll Area for Classes
        self.class_scroll = QScrollArea()
        self.class_scroll.setWidgetResizable(True)
        self.class_scroll.setStyleSheet("background: transparent; border: none;")
        
        # Container for checkboxes
        self.class_checkbox_container = QWidget()
        self.class_grid_layout = QGridLayout(self.class_checkbox_container)
        self.class_grid_layout.setSpacing(10)
        self.class_grid_layout.setContentsMargins(0, 0, 0, 0)
        
        self.class_scroll.setWidget(self.class_checkbox_container)
        layout.addWidget(self.class_scroll)
    
    def set_backend_detector(self, backend_detector):
        """
         NEW: Link backend detector after initialization
        Enables automatic syncing of selected classes
        """
        self.backend_detector = backend_detector
        # Initialize previous state
        self.prev_state = {name: cb.isChecked() for name, cb in self.checkboxes.items()}
        
        # Connect change handler
        for name, cb in self.checkboxes.items():
            cb.stateChanged.connect(lambda state, n=name: self._on_checkbox_changed(n, state))
        
        # Send initial selection
        self._sync_to_backend()
        
        print(f" ClassSelectionPanel linked to backend detector")
    
    def populate_classes(self, class_names, default_checked=None):
        """Populate the panel with class checkboxes"""
        if default_checked is None:
            default_checked = ["person"]
        
        # Clear existing
        while self.class_grid_layout.count():
            item = self.class_grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        self.checkboxes.clear()
        
        # Create checkboxes
        row = 0
        
        for cls_name in class_names:
            checkbox = QCheckBox(cls_name.capitalize())
            checkbox.setCursor(Qt.PointingHandCursor)
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    spacing: 8px;
                    color: {TEXT_COLOR};
                    font-size: 14px;
                    font-weight: normal;
                    padding: 4px;
                }}
                QCheckBox::indicator {{
                    width: 20px;
                    height: 20px;
                    border: 1px solid #4B5563;
                    border-radius: 6px;
                    background-color: {BACKGROUND_COLOR};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {PRIMARY_COLOR};
                    border: 1px solid {PRIMARY_COLOR};
                }}
                QCheckBox::indicator:hover {{
                    border: 1px solid {PRIMARY_COLOR};
                }}
            """)
            
            # Check if should be checked by default
            checkbox.setChecked(cls_name.lower() in [c.lower() for c in default_checked])
            
            self.class_grid_layout.addWidget(checkbox, row, 0)
            self.checkboxes[cls_name] = checkbox
            row += 1
        
        # If backend already linked, connect handlers
        if self.backend_detector:
            self.prev_state = {name: cb.isChecked() for name, cb in self.checkboxes.items()}
            for name, cb in self.checkboxes.items():
                cb.stateChanged.connect(lambda state, n=name: self._on_checkbox_changed(n, state))
            self._sync_to_backend()
    
    def _on_checkbox_changed(self, name, state):
        """
        Handle checkbox state changes and sync to backend
        """
        print(f"📘 Checkbox '{name}' is now {'checked' if state else 'unchecked'}")
        self._sync_to_backend()
    
    def _sync_to_backend(self):
        """
        ✅ FIXED: Sync selected classes to backend detector with validation
        """
        if not self.backend_detector:
            print("⚠️ No backend detector linked, skipping sync")
            return
        
        # Get selected class names
        selected_names = [name for name, cb in self.checkboxes.items() if cb.isChecked()]
        
        if not selected_names:
            print("⚠️ No classes selected")
            return
        
        # Convert names to IDs
        try:
            # ✅ Verify backend_detector has model and names
            if not hasattr(self.backend_detector, 'model'):
                print("❌ Backend detector has no model attribute")
                return
            
            if not hasattr(self.backend_detector.model, 'names'):
                print("❌ Backend detector model has no names attribute")
                return
            
            model_names = self.backend_detector.model.names
            print(f"📋 Available model classes: {model_names}")
            
            # Map selected names to class IDs
            selected_ids = []
            for cls_id, cls_name in model_names.items():
                if cls_name in selected_names:
                    selected_ids.append(cls_id)
            
            if not selected_ids:
               print(f"⚠️ No matching IDs found for selected names: {selected_names}")
               return
            
            print(f"📤 Syncing to backend: {selected_names} → IDs: {selected_ids}")
            
            # ✅ Send to backend using correct method
            if hasattr(self.backend_detector, 'update_selected_classes_for_backend'):
                self.backend_detector.update_selected_classes_for_backend(selected_ids)
                print(f"✅ Synced to backend: {selected_ids}")
            else:
               print("❌ Backend detector missing update_selected_classes_for_backend method")
            
        except Exception as e:
            print(f"❌ Error syncing to backend: {e}")

    def get_selected_classes(self):
        """Get list of selected class names"""
        return [name for name, cb in self.checkboxes.items() if cb.isChecked()]
    
    def append_log(self, message, log_type="INFO"):
        """Add log entry using shared panel"""
        if self.log_panel:
            self.log_panel.append_log(message, log_type)


    def get_selected_class_ids(self):
        """
        Get selected class IDs directly
        """
        if not self.backend_detector:
            return []
        
        selected_names = self.get_selected_classes()
        
        try:
            selected_ids = [
                cls_id for cls_id, cls_name in self.backend_detector.model.names.items()
                if cls_name in selected_names
            ]
            return selected_ids
        except Exception as e:
           print(f"❌ Error getting class IDs: {e}")
           return []
    
    def set_checkboxes_enabled(self, enabled):
        """Enable or disable all checkboxes"""
        for checkbox in self.checkboxes.values():
            checkbox.setEnabled(enabled)
    
    def connect_change_handler(self, handler):
        """
        Connect external handler to checkbox changes
        (Optional - for backwards compatibility)
        """
        for name, checkbox in self.checkboxes.items():
            checkbox.stateChanged.connect(lambda state, n=name: handler(n, state))

class LogPanel(QWidget):
    log_signal = pyqtSignal(str, str)
    """
    Enhanced log panel with filtering, search, and rich formatting.
    """
    
    def __init__(self, title="System Logs", parent=None):
        super().__init__(parent)
        self.title = title
        self.log_is_empty = True
        self.all_logs = []
        self.current_filter = "ALL"
        self.log_signal.connect(self.append_log)
        
        
        #  ADD: Mutex for thread safety
        self._log_lock = threading.Lock()
        self._refresh_lock = threading.Lock()
        
        #  ADD: Debounce timer for filter changes
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._do_refresh_display)
        self._pending_filter = None
        
        #  ADD: Track refresh state
        self._is_refreshing = False
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the enhanced log panel UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header with title and controls
        
        log_header = QHBoxLayout()
        
        log_title = QLabel(self.title)
        log_title.setObjectName("SectionTitle")
        log_header.addWidget(log_title)
        log_header.addStretch()
        
        # Clear button
        self.btn_clear_logs = QPushButton("Clear")
        self.btn_clear_logs.setIcon(
            QApplication.style().standardIcon(QStyle.SP_TrashIcon)
        )
        self.btn_clear_logs.setCursor(Qt.PointingHandCursor)
        self.btn_clear_logs.setFixedSize(80, 30)
        self.btn_clear_logs.setStyleSheet(
            f"background-color: {BACKGROUND_COLOR}; color: {SECONDARY_TEXT}; "
            "border: 1px solid #374151; border-radius: 4px; font-size: 12px;"
        )
        self.btn_clear_logs.clicked.connect(self.clear_logs)
        log_header.addWidget(self.btn_clear_logs)
        
        layout.addLayout(log_header)
        
        
        # Filter buttons
        
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(5)
        
        self.filter_buttons = {}
        filter_configs = {
        "ALL": ("📋", "Show all logs"),
        "INFO": ("ℹ️", "Show info logs only"),
        "WARNING": ("⚠️", "Show warnings only"),
        "ERROR": ("❌", "Show errors only"),
        "VIOLATION": ("🚨", "Show violations only")
        }
        for filter_type, (icon, tooltip) in filter_configs.items():
            btn = QPushButton(icon)  # ← Just icon, no text
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(40, 32)  # ← Smaller, icon-only buttons
            btn.setToolTip(tooltip)  # ← Tooltip shows on hover
            btn.clicked.connect(lambda checked, ft=filter_type: self.set_filter(ft))
            self.filter_buttons[filter_type] = btn
            filter_layout.addWidget(btn)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        self.update_filter_button_styles()
        
        
        # Stats bar
        
        self.stats_label = QLabel("Total: 0 | Violations: 0")
        self.stats_label.setStyleSheet(
            f"color: {SECONDARY_TEXT}; font-size: 11px; "
            "padding: 5px; background-color: rgba(255,255,255,0.05); "
            "border-radius: 4px;"
        )
        layout.addWidget(self.stats_label)
        
        
        # Scrollable log area
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        self.log_container = QWidget()
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setSpacing(10)
        self.log_layout.addStretch()
        
        scroll.setWidget(self.log_container)
        layout.addWidget(scroll)
        
        # Empty state placeholder
        self.empty_state = QLabel("No logs yet")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.setStyleSheet(
            f"color: {SECONDARY_TEXT}; font-size: 14px; "
            "padding: 20px; font-style: italic;"
        )
        self.log_layout.insertWidget(0, self.empty_state)
    
    def set_filter(self, filter_type):
        """
        Debounced filter switching to prevent rapid-click crashes
        """
        # Store pending filter
        self._pending_filter = filter_type
        
        #  Cancel any pending refresh
        if self._filter_timer.isActive():
            self._filter_timer.stop()
        
        #  Update button styles immediately (visual feedback)
        self.current_filter = filter_type
        self.update_filter_button_styles()
        
        # Debounce: only refresh after 150ms of no clicks
        self._filter_timer.start(150)
    
    def _do_refresh_display(self):
        """
         Actual refresh implementation with locking
        """
        #  Prevent concurrent refreshes
        if not self._refresh_lock.acquire(blocking=False):
            print("⚠️ Refresh already in progress, skipping")
            return
        
        try:
            self._is_refreshing = True
            
            #  Use pending filter if available
            if self._pending_filter:
                self.current_filter = self._pending_filter
                self._pending_filter = None
            
            # Update stats
            self.update_stats()
            
            # Clear display SAFELY
            self._safe_clear_display()
            
            # Filter logs
            if self.current_filter == "ALL":
                filtered_logs = self.all_logs
            else:
                filtered_logs = [
                    log for log in self.all_logs 
                    if log["type"] == self.current_filter
                ]
            
            # Show empty state if needed
            if not filtered_logs:
                try:
                    if hasattr(self, 'empty_state'):
                        self.empty_state.show()
                        self.log_is_empty = True
                except RuntimeError:
                    pass
                return
            
            # Hide empty state
            try:
                if hasattr(self, 'empty_state'):
                    self.empty_state.hide()
                    self.log_is_empty = False
            except RuntimeError:
                pass
            
            # Add filtered logs (newest first)
            logs_to_display = filtered_logs[-100:]
            for log_entry in reversed(logs_to_display):
                self._add_log_to_display(log_entry)
        
        finally:
            self._is_refreshing = False
            self._refresh_lock.release()
    
    def _safe_clear_display(self):
        """
          Safely clear display without race conditions
        """
        #  Collect items to delete FIRST (while holding layout)
        items_to_delete = []
        
        while self.log_layout.count() > 1:
            item = self.log_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget and widget != getattr(self, 'empty_state', None):
                    items_to_delete.append(widget)
        
        #  Delete widgets AFTER releasing layout
        # This prevents double-deletion race conditions
        for widget in items_to_delete:
            try:
                #  Check if widget still exists
                if widget and not sip.isdeleted(widget):
                    widget.deleteLater()
            except RuntimeError:
                # Already deleted
                pass

    def update_filter_button_styles(self):
        """Update filter button appearance (icon-only version)"""
        for filter_type, btn in self.filter_buttons.items():
            if filter_type == self.current_filter:
                # Active filter - highlighted
                btn.setStyleSheet(
                    f"background-color: {PRIMARY_COLOR}; color: white; "
                    "border: none; border-radius: 6px; font-size: 18px; "
                    "padding: 5px;"
                )
            else:
                # Inactive filter
                btn.setStyleSheet(
                    f"background-color: {CARD_COLOR}; color: {SECONDARY_TEXT}; "
                    "border: 1px solid #374151; border-radius: 6px; font-size: 18px; "
                    "padding: 5px;"
                )
        
    def append_log(self, message, log_type="INFO", metadata=None):
        """
         Thread-safe log appending with lock
        """
        #  Prevent concurrent appends
        with self._log_lock:
            try:
                # Create log entry
                log_entry = {
                    "timestamp": datetime.datetime.now(),
                    "message": message,
                    "type": log_type,
                    "metadata": metadata or {}
                }
                
                # Store in all_logs
                self.all_logs.append(log_entry)
                
                # Limit stored logs
                MAX_STORED_LOGS = 1000
                if len(self.all_logs) > MAX_STORED_LOGS:
                    self.all_logs = self.all_logs[-MAX_STORED_LOGS:]
                
                # Update stats
                self.update_stats()
                
                #  Only add to display if matches filter AND not currently refreshing
                if (self.current_filter == "ALL" or self.current_filter == log_type) and not self._is_refreshing:
                    # Hide empty state if visible
                    if self.log_is_empty:
                        try:
                            if hasattr(self, 'empty_state'):
                                self.empty_state.hide()
                                self.log_is_empty = False
                        except RuntimeError:
                            pass
                    
                    # Create log widget
                    if log_type == "VIOLATION":
                        log_widget = self._create_violation_log_widget(
                            log_entry["timestamp"].strftime('%H:%M:%S'),
                            message,
                            metadata
                        )
                    else:
                        log_widget = self._create_standard_log_widget(
                            log_entry["timestamp"].strftime('%H:%M'),
                            message,
                            log_type
                        )
                    
                    # Insert at top
                    self.log_layout.insertWidget(0, log_widget)
                    
                    # Keep display limit
                    if self.log_layout.count() > 101:
                        item = self.log_layout.itemAt(self.log_layout.count() - 2)
                        if item and item.widget():
                            widget = item.widget()
                            if widget != getattr(self, 'empty_state', None):
                                try:
                                    if not sip.isdeleted(widget):
                                        widget.deleteLater()
                                except RuntimeError:
                                    pass
        
            except Exception as e:
                print(f"❌ Error appending log: {e}")
        
    def _add_log_to_display(self, log_entry):
        """Add a single log entry to the display"""
        # Hide empty state
        if self.log_is_empty and self.empty_state:
            try:
                self.empty_state.hide()
                self.log_is_empty = False
            except RuntimeError:
                pass
        
        timestamp = log_entry["timestamp"].strftime('%H:%M:%S')
        message = log_entry["message"]
        log_type = log_entry["type"]
        metadata = log_entry["metadata"]
        
        # Create log widget based on type
        if log_type == "VIOLATION":
            log_widget = self._create_violation_log_widget(timestamp, message, metadata)
        else:
            log_widget = self._create_standard_log_widget(timestamp, message, log_type)
        
        # Insert at top
        self.log_layout.insertWidget(0, log_widget)
        
        # Keep max 100 logs in display
        if self.log_layout.count() > 100:
            item = self.log_layout.itemAt(self.log_layout.count() - 2)
            if item and item.widget() and item.widget() != self.empty_state:
                try:
                    item.widget().deleteLater()
                except RuntimeError:
                    pass
    
    def _create_standard_log_widget(self, timestamp, message, log_type):
        """Create standard log entry widget"""
        if log_type == "ERROR":
            icon = "❌"
            text_color = "#EF4444"
        elif log_type == "WARNING":
            icon = "⚠️"
            text_color = "#F59E0B"
        else:  # INFO
            icon = "ℹ️"
            text_color = TEXT_COLOR
        
        formatted_msg = f"{icon} [{timestamp}] {message}"
        
        lbl = QLabel(formatted_msg)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {text_color}; font-size: 14px; padding: 8px 0; "
            "border-bottom: 1px solid #374151;"
        )
        
        return lbl
    
    def _create_violation_log_widget(self, timestamp, message, metadata):
        """Create enhanced violation log entry widget"""
        container = QFrame()
        container.setStyleSheet(
            "background-color: rgba(239, 68, 68, 0.1); "
            "border: 2px solid #EF4444; border-radius: 8px; "
            "padding: 10px;"
        )
        
        layout = QVBoxLayout(container)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header with icon and timestamp
        header_layout = QHBoxLayout()
        header_label = QLabel(f"🚨 VIOLATION DETECTED")
        header_label.setStyleSheet(
            "color: #EF4444; font-size: 15px; font-weight: bold;"
        )
        header_layout.addWidget(header_label)
        
        time_label = QLabel(f"[{timestamp}]")
        time_label.setStyleSheet("color: #EF4444; font-size: 12px;")
        header_layout.addWidget(time_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(
            "color: #EF4444; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(msg_label)
        
        # Metadata details (if available)
        if metadata:
            details_layout = QVBoxLayout()
            details_layout.setSpacing(3)
            
            if "person_id" in metadata:
                person_lbl = QLabel(f"  • Person ID: {metadata['person_id']}")
                person_lbl.setStyleSheet("color: #FCA5A5; font-size: 12px;")
                details_layout.addWidget(person_lbl)
            
            if "missing_items" in metadata:
                items_str = ", ".join(metadata['missing_items'])
                items_lbl = QLabel(f"  • Missing: {items_str}")
                items_lbl.setStyleSheet("color: #FCA5A5; font-size: 12px;")
                details_layout.addWidget(items_lbl)
            
            if "severity" in metadata:
                severity_lbl = QLabel(f"  • Severity: {metadata['severity']}")
                severity_lbl.setStyleSheet("color: #FCA5A5; font-size: 12px;")
                details_layout.addWidget(severity_lbl)
            
            layout.addLayout(details_layout)
        
        return container
    
    def refresh_display(self):
        """
         PUBLIC: Request refresh (debounced for safety)
        """
        # Use debounced refresh instead of direct call
        if self._filter_timer.isActive():
            self._filter_timer.stop()
        self._filter_timer.start(100)
    
    def update_stats(self):
        """Update statistics label with filter info"""
        total = len(self.all_logs)
        violations = sum(1 for log in self.all_logs if log["type"] == "VIOLATION")
        errors = sum(1 for log in self.all_logs if log["type"] == "ERROR")
        warnings = sum(1 for log in self.all_logs if log["type"] == "WARNING")
        
        # Show filter status
        if self.current_filter == "ALL":
            filter_text = "All logs"
            filtered_count = total
        else:
            filter_text = self.current_filter
            filtered_count = sum(1 for log in self.all_logs if log["type"] == self.current_filter)
        
        stats_text = (
            f"{filter_text} ({filtered_count}) | "
            f"Total: {total} | Violations: {violations} | "
            f"Errors: {errors} | Warnings: {warnings}"
        )
        self.stats_label.setText(stats_text)
    
    def clear_logs(self):
        """Clear all log entries"""
        # Clear stored logs
        self.all_logs.clear()
        
        # Clear display
        while self.log_layout.count() > 1:
            item = self.log_layout.takeAt(0)
            widget = item.widget()
            if widget:
                try:
                    widget.deleteLater()
                except RuntimeError:
                    pass
        
        # Reset empty state
        self.empty_state = QLabel("No logs yet")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.setStyleSheet(
            f"color: {SECONDARY_TEXT}; font-size: 14px; "
            "padding: 20px; font-style: italic;"
        )
        
        self.log_layout.insertWidget(0, self.empty_state)
        self.empty_state.show()
        self.log_is_empty = True
        
        # Update stats
        self.update_stats()
    
    def get_violation_count(self):
        """Get total number of violations logged"""
        return sum(1 for log in self.all_logs if log["type"] == "VIOLATION")
    
    def export_logs(self, filepath):
        """Export logs to text file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"=== {self.title} Export ===\n")
                f.write(f"Generated: {datetime.datetime.now()}\n")
                f.write(f"Total Logs: {len(self.all_logs)}\n\n")
                
                for log in self.all_logs:
                    timestamp = log["timestamp"].strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"[{timestamp}] [{log['type']}] {log['message']}\n")
                    
                    if log["metadata"]:
                        f.write(f"  Metadata: {log['metadata']}\n")
                    f.write("\n")
            
            return True
        except Exception as e:
            print(f"❌ Error exporting logs: {e}")
            return False

class ViolationDataManager:
    """
    Manages violation data storage including images and metadata.
    Stores: cropped person images, full frame images, JSON metadata.
    """
    
    def __init__(self, base_dir="violation_data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.log_panel = None
        
        # Create subdirectories
        self.images_dir = self.base_dir / "images"
        self.cropped_dir = self.images_dir / "cropped"
        self.full_frame_dir = self.images_dir / "full_frame"
        self.metadata_dir = self.base_dir / "metadata"
        
        for directory in [self.images_dir, self.cropped_dir, 
                         self.full_frame_dir, self.metadata_dir]:
            directory.mkdir(exist_ok=True)
        
        self.violation_log = []
        print(f" ViolationDataManager initialized at: {self.base_dir}")
    
    def capture_violation(self, violation_data, full_frame, detection_frame):
        """
        Capture and store violation data with images.
        
        Args:
            violation_data: dict with violation details
            full_frame: original frame (BGR)
            detection_frame: frame with detection boxes (BGR)
        
        Returns:
            violation_id: unique ID for this violation
        """
        try:
            # Generate unique violation ID
            violation_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            # Extract person bbox
            bbox = violation_data.get("person_bbox")
            if not bbox:
                print("⚠️ No bbox found in violation data")
                return None
             
            x1, y1, x2, y2 = bbox
            
            
            # 1. Crop person from frame
            
            cropped_person = full_frame[y1:y2, x1:x2].copy()
            
            # Add violation labels to cropped image
            cropped_with_labels = self._add_labels_to_crop(
                cropped_person.copy(),
                violation_data["missing"]
            )
            
            # Save cropped image
            crop_path = self.cropped_dir / f"{violation_id}_crop.jpg"
            cv2.imwrite(str(crop_path), cropped_with_labels)
            
            
            # 2. Save full frame with highlights
            
            full_with_highlight = detection_frame.copy()
            
            # Add extra emphasis (thicker red box)
            cv2.rectangle(full_with_highlight, (x1, y1), (x2, y2), 
                         (0, 0, 255), 6)
            
            # Add timestamp watermark
            timestamp_text = violation_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(full_with_highlight, timestamp_text, 
                       (10, full_with_highlight.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            full_path = self.full_frame_dir / f"{violation_id}_full.jpg"
            cv2.imwrite(str(full_path), full_with_highlight)
            
            
            # 3. Create metadata JSON
            
            metadata = {
                "violation_id": violation_id,
                "timestamp": violation_data["timestamp"].isoformat(),
                "person_bbox": bbox,
                "missing_items": violation_data["missing"],
                "severity": violation_data.get("severity", "MEDIUM"),
                "person_confidence": violation_data.get("person_confidence", 0.0),
                "frame_shape": violation_data.get("frame_shape"),
                "images": {
                    "cropped": str(crop_path.relative_to(self.base_dir)),
                    "full_frame": str(full_path.relative_to(self.base_dir))
                }
            }
            
            # Save metadata
            meta_path = self.metadata_dir / f"{violation_id}_meta.json"
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Add to log
            self.violation_log.append(metadata)
            
            self.append_log(f" Violation captured: {violation_id}")
            return violation_id
        
        except Exception as e:
            print(f"❌ Error capturing violation: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _add_labels_to_crop(self, crop_img, missing_items):
        """Add violation labels to cropped person image"""
        h, w = crop_img.shape[:2]
        
        # Create overlay for semi-transparent background
        overlay = crop_img.copy()
        
        # Draw labels
        y_offset = 30
        for item in missing_items:
            label_text = f"❌ {item}"
            
            # Get text size
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            text_size = cv2.getTextSize(label_text, font, font_scale, thickness)[0]
            
            # Draw background rectangle
            cv2.rectangle(overlay, 
                         (5, y_offset - text_size[1] - 5),
                         (text_size[0] + 15, y_offset + 5),
                         (0, 0, 255), -1)
            
            y_offset += text_size[1] + 15
        
        # Blend overlay with original
        crop_img = cv2.addWeighted(overlay, 0.7, crop_img, 0.3, 0)
        
        # Draw text on top
        y_offset = 30
        for item in missing_items:
            label_text = f"❌ {item}"
            cv2.putText(crop_img, label_text, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += 30
        
        return crop_img
    
    def append_log(self, message, log_type="INFO"):
        """Add log entry using shared panel"""
        if self.log_panel:
            self.log_panel.log_signal.emit(message, log_type)
    

    def get_violation_by_id(self, violation_id):
        """Retrieve violation data by ID"""
        for violation in self.violation_log:
            if violation["violation_id"] == violation_id:
                return violation
        return None
    
    def get_recent_violations(self, count=10):
        """Get most recent violations"""
        return self.violation_log[-count:]
    
    def get_violations_in_timerange(self, start_time, end_time):
        """Get violations within time range"""
        filtered = []
        for v in self.violation_log:
            v_time = datetime.datetime.fromisoformat(v["timestamp"])
            if start_time <= v_time <= end_time:
                filtered.append(v)
        return filtered
    
    def capture_batch_violation(self, violations_list, full_frame, detection_frame):
        
        # Capture multiple violations from the same frame in one batch.
        try:
            # Generate unique batch ID
            batch_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            cropped_paths = []
            person_data = []
            
            # Process each person's violation
            for idx, violation in enumerate(violations_list):
                bbox = violation.get("person_bbox")
                if not bbox:
                    continue
                
                x1, y1, x2, y2 = bbox
                
                # Crop person from frame
                cropped_person = full_frame[y1:y2, x1:x2].copy()
                
                # Add violation labels to cropped image
                cropped_with_labels = self._add_labels_to_crop(
                    cropped_person.copy(),
                    violation["missing"]
                )
                
                # Save cropped image
                crop_filename = f"{batch_id}_person_{idx+1}_crop.jpg"
                crop_path = self.cropped_dir / crop_filename
                cv2.imwrite(str(crop_path), cropped_with_labels)
                
                cropped_paths.append(crop_path)
                
                # Store person metadata
                person_data.append({
                    "person_id": idx + 1,
                    "bbox": bbox,
                    "missing_items": violation["missing"],
                    "confidence": violation.get("person_confidence", 0.0),
                    "severity": violation.get("severity", "MEDIUM")
                })
            
            # Save full frame with all violations highlighted
            full_with_highlights = detection_frame.copy()
            
            # Add extra emphasis for all persons
            for violation in violations_list:
                bbox = violation.get("person_bbox")
                if bbox:
                    x1, y1, x2, y2 = bbox
                    cv2.rectangle(full_with_highlights, (x1, y1), (x2, y2), 
                                (0, 0, 255), 6)
                    
                    # Add person number
                    person_num = violations_list.index(violation) + 1
                    cv2.putText(full_with_highlights, f"Person {person_num}", 
                              (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 
                              (0, 0, 255), 2)
            
            # Add timestamp watermark
            timestamp_text = violations_list[0]["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(full_with_highlights, timestamp_text, 
                       (10, full_with_highlights.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Add total count
            count_text = f"Total Violations: {len(violations_list)}"
            cv2.putText(full_with_highlights, count_text, 
                       (10, full_with_highlights.shape[0] - 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            full_path = self.full_frame_dir / f"{batch_id}_full.jpg"
            cv2.imwrite(str(full_path), full_with_highlights)
            
            # Create batch metadata
            metadata = {
                "batch_id": batch_id,
                "timestamp": violations_list[0]["timestamp"].isoformat(),
                "total_persons": len(violations_list),
                "persons": person_data,
                "severity": self._calculate_batch_severity(violations_list),
                "frame_shape": violations_list[0].get("frame_shape"),
                "images": {
                    "cropped": [str(p.relative_to(self.base_dir)) for p in cropped_paths],
                    "full_frame": str(full_path.relative_to(self.base_dir))
                }
            }
            
            # Save metadata
            meta_path = self.metadata_dir / f"{batch_id}_meta.json"
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Add to log
            self.violation_log.append(metadata)
            
            self.append_log(f"✅ Batch violation captured: {batch_id} ({len(violations_list)} persons)")
            return batch_id, cropped_paths
        
        except Exception as e:
            print(f"❌ Error capturing batch violation: {e}")
            import traceback
            traceback.print_exc()
            return None, []

    def _calculate_batch_severity(self, violations_list):
        """Calculate overall severity for batch of violations"""
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        max_severity = "LOW"
        
        for violation in violations_list:
            severity = violation.get("severity", "MEDIUM")
            if severities.index(severity) > severities.index(max_severity):
                max_severity = severity
        
        return max_severity

    def export_summary(self, output_file="violation_summary.txt"):
        """Export violation summary report"""
        try:
            output_path = self.base_dir / output_file
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("="*60 + "\n")
                f.write("VIOLATION SUMMARY REPORT\n")
                f.write("="*60 + "\n\n")
                
                f.write(f"Total Violations: {len(self.violation_log)}\n")
                f.write(f"Report Generated: {datetime.datetime.now()}\n")
                f.write(f"Data Directory: {self.base_dir}\n\n")
                
                # Count by severity
                severity_counts = {}
                missing_items_counts = {}
                
                
                for v in self.violation_log:

                    # ---- SINGLE VIOLATION ----
                    if "missing_items" in v:
                        severity = v.get("severity", "UNKNOWN")
                        severity_counts[severity] = severity_counts.get(severity, 0) + 1

                        for item in v["missing_items"]:
                            missing_items_counts[item] = missing_items_counts.get(item, 0) + 1

                    # ---- BATCH VIOLATION ----
                    elif "persons" in v:
                        severity = v.get("severity", "UNKNOWN")
                        severity_counts[severity] = severity_counts.get(severity, 0) + 1

                        for person in v["persons"]:
                            for item in person.get("missing_items", []):
                                missing_items_counts[item] = missing_items_counts.get(item, 0) + 1


                f.write("VIOLATIONS BY SEVERITY:\n")
                for severity, count in sorted(severity_counts.items()):
                    f.write(f"  {severity}: {count}\n")
                
                f.write("\nMOST COMMON VIOLATIONS:\n")
                for item, count in sorted(missing_items_counts.items(), 
                                         key=lambda x: x[1], reverse=True):
                    f.write(f"  {item}: {count}\n")
                
                f.write("\n" + "="*60 + "\n")
                f.write("DETAILED VIOLATIONS:\n")
                f.write("="*60 + "\n\n")
                
                for v in self.violation_log:
                    if "violation_id" in v:
                        f.write(f"ID: {v['violation_id']}\n")
                        f.write(f"Missing: {', '.join(v['missing_items'])}\n")
                    elif "batch_id" in v:
                        f.write(f"Batch ID: {v['batch_id']}\n")
                        f.write(f"Total Persons: {v['total_persons']}\n")
                        for p in v["persons"]:
                            f.write(f"  Person {p['person_id']} missing: "f"{', '.join(p['missing_items'])}\n")

                    f.write(f"Time: {v['timestamp']}\n")
                    f.write(f"Severity: {v['severity']}\n")
                    f.write(f"Images:\n")
                    f.write(f"  - Cropped: {v['images']['cropped']}\n")
                    f.write(f"  - Full: {v['images']['full_frame']}\n")
                    f.write("-"*60 + "\n\n")
            
            self.append_log(f" Summary exported to: {output_path}")
            return str(output_path)
        
        except Exception as e:
            print(f"❌ Error exporting summary: {e}")
            return None

class SaveDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_panel = None
        self.setWindowTitle("Start Recording")
        self.setFixedWidth(450)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {CARD_COLOR};
                border: 1px solid #374151;
                border-radius: 8px;
            }}
            QLabel {{
                color: {TEXT_COLOR};
                font-size: 14px;
            }}
            QLineEdit {{
                background-color: {BACKGROUND_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid #374151;
                padding: 8px;
                border-radius: 4px;
            }}
            QComboBox {{
                background-color: {BACKGROUND_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid #374151;
                padding: 8px;
                border-radius: 4px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {CARD_COLOR};
                color: {TEXT_COLOR};
                selection-background-color: {PRIMARY_COLOR};
                selection-color: white;
                border: 1px solid #374151;
            }}
            QPushButton {{
                background-color: {PRIMARY_COLOR};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #0284c7;
            }}
            QPushButton#Secondary {{
                background-color: transparent;
                border: 1px solid #374151;
                color: {SECONDARY_TEXT};
            }}
            QPushButton#Secondary:hover {{
                background-color: #374151;
                color: {TEXT_COLOR};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Recording Options")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        # Save Type
        layout.addWidget(QLabel("Save Format:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Video (.mp4)", "Frames (.jpg)"])
        layout.addWidget(self.type_combo)
        
        # Location
        layout.addWidget(QLabel("Save Location:"))
        loc_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(os.path.join(os.getcwd(), "Saved_Detections"))
        loc_layout.addWidget(self.path_input)
        
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("Secondary")
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self.browse_folder)
        loc_layout.addWidget(browse_btn)
        layout.addLayout(loc_layout)
        
        # Folder/File Name
        layout.addWidget(QLabel("Subfolder Name (Optional):"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., session_01 (leave empty for timestamp)")
        layout.addWidget(self.name_input)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("Secondary")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Start Recording")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)

    def append_log(self, message, log_type="INFO"):
        """Add log entry using shared panel"""
        if self.log_panel:
            self.log_panel.append_log(message, log_type)
    

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder:
            self.path_input.setText(folder)

    def get_data(self):
        save_type = "video" if "Video" in self.type_combo.currentText() else "frames"
        base_path = self.path_input.text()
        subfolder = self.name_input.text().strip()
        
        if not subfolder:
            from datetime import datetime
            subfolder = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            
        full_path = os.path.join(base_path, subfolder)
        return save_type, full_path

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)  # For MonitorScreen
    violation_pixmap_signal = pyqtSignal(QImage)  # For ViolationScreen
    log_signal = pyqtSignal(str)
    model_loaded_signal = pyqtSignal(list)

    def __init__(self, source=0, model_path="epoch31.pt", tracking_path=None, use_gpu=False,ui_label=None,log_callback=None):
        super().__init__()
        self.source = source
        self.model_path = model_path
        self.tracking_path = tracking_path
        self.use_gpu = use_gpu
        self.ui_label = ui_label
        self.log_panel = None
        self.violation_ui_label = None  
        self.running = True
        self._updating=False
        self.log_callback = log_callback  # ✅ Store callback
        #  ADD: Connection stability tracking
        self._connection_stable = False
        self._frame_count = 0
        self._last_frame_time = time.time()
        #  NEW: Aggressive frame rate limiting
        self._last_emit_time = 0
        self._last_violation_emit_time = 0
        self._min_emit_interval = 1.0 / 25.0  # Max 25 FPS for UI
        
        self._frame_lock = threading.Lock()
        self._violation_lock = threading.Lock()
        self.backendUI = None
        
        self._last_violation_emit = 0  
        self._backend_run_thread = None
        self._backend_ready_event = threading.Event()
        self._pending_mode = None
    
    def send_log(self, message, log_type="INFO"):
        """✅ Fixed _log method"""
        if self.log_callback:
            try:
                self.log_callback(message, log_type)
            except Exception as e:
                print(f"⚠️ Log callback error: {e}")

    def append_log(self, message, log_type="INFO"):
        """Add log entry using shared panel"""
        if self.log_panel:
            self.log_panel.append_log(message, log_type)
    
    

    def is_connection_stable(self):
        """
         NEW: Check if connection is stable (for IP cameras)
        """
        try:
            # Check frame rate
            current_time = time.time()
            time_since_last_frame = current_time - self._last_frame_time
            
            # If no frames for >2 seconds, unstable
            if time_since_last_frame > 2.0:
                return False
            
            # If frame count > 30 and recent frame, stable
            if self._frame_count > 30 and time_since_last_frame < 0.5:
                self._connection_stable = True
                return True
            
            return self._connection_stable
            
        except Exception:
            return False
    
    def set_violation_ui_label(self, label):
        """  Set violation screen label"""
        try:
            if label is None:
                return
            
            if not isinstance(label, QLabel):
                print(f"⚠️ Invalid label type: {type(label)}")
                return
            
            try:
                _ = label.isVisible()
            except RuntimeError:
                print("⚠️ Cannot set violation label: widget deleted")
                return
            
            self.violation_ui_label = label
            print(" Violation UI label set")
            
        except Exception as e:
            print(f"❌ Error setting violation label: {e}")
    
    def _start_backend_run_thread(self):
        """Start backendUI.run() inside a standard Python thread (daemon)."""
        def target():
            try:
                self.backendUI.run()
            except Exception as e:
                self.log_signal.emit(f"❌ backend run error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self._backend_ready_event.clear()

        self._backend_run_thread = threading.Thread(target=target, daemon=True)
        self._backend_run_thread.start()

    def run(self):
        """Main thread loop: instantiate backend, start backend run thread, handle frame callbacks."""
        try:
            from objectTracking import UI
        except Exception as e:
            self.log_signal.emit(f"❌ import error: {e}")
            return

        # Try to instantiate backend (with retry for network sources)
        connected = False
        while not connected and self.running:
            try:
                self.backendUI = UI(source=self.source, model_path=self.model_path,tracking_path=self.tracking_path,use_gpu=self.use_gpu,log_callback=lambda msg, log_type="INFO": self.log_signal.emit(msg))
                
                #  Set BOTH frame callbacks
                self.backendUI.backend.frame_callback = self.get_frames_from_backend
                self.backendUI.backend.violation_frame_callback = self.get_violation_frames_from_backend
                
                connected = True
                self._backend_ready_event.set()
                
                # Emit class names for UI
                try:
                    class_names = list(self.backendUI.backend.Detector.model.names.values())
                    self.model_loaded_signal.emit(class_names)
                except Exception as e:
                   print(f"❌ Error emitting model classes: {e}")
                    
            except Exception as e:

                # self.log_signal.emit(f"❌ Failed to Connect With The Camera Source:\n{e}\n\n💡 Tips:\n• Check network connection\n• Verify IP address and port\n• Ensure camera is streaming\n• Try format: http://IP:PORT/video_feed")
                traceback.print_exc()
                # Retry only for network-like sources
                if isinstance(self.source, str) and ("http" in self.source.lower() or "rtsp" in self.source.lower()):
                    time.sleep(1.0)
                    continue
                else:
                    return

        if not self.running:
            # User requested stop while connecting
            try:
                if self.backendUI:
                    self.backendUI.stop_all_modes()
            except Exception:
                pass
            return

        # self.log_signal.emit(f" Backend instantiated for source: {self.source}")

        # Apply any pending mode (requested by UI before backend ready)
        if self._pending_mode:
            try:
                self.backendUI.setMode(self._pending_mode)
                self._pending_mode = None
            except Exception:
                pass

        # Start backend.run() inside a normal Python thread
        try:
            self._start_backend_run_thread()
        except Exception as e:
           # self.log_signal.emit(f"❌ Failed to start backend thread: {e}")
            traceback.print_exc()
            return

        # Keep this QThread alive until told to stop
        try:
            while self.running:
                time.sleep(0.05)
        except Exception as e:
            # self.log_signal.emit(f"❌ Error in VideoThread main loop: {e}")
            traceback.print_exc()
        finally:
            # Clean up
            try:
                if self.backendUI:
                    try:
                        self.backendUI.stop_all_modes()
                    except Exception:
                        pass
                    if hasattr(self.backendUI, "stop"):
                        try:
                            self.backendUI.stop()
                        except Exception:
                            pass
            except Exception:
                pass

            # Wait for backend run thread to exit
            if self._backend_run_thread and self._backend_run_thread.is_alive():
                self.log_signal.emit("⏳ waiting for backend thread to finish...")
                self._backend_run_thread.join(timeout=2.0)

            self.log_signal.emit("🔌 VideoThread exiting cleanly.")
    
    def get_frames_from_backend(self, frame):
        """
         Scale in worker thread like working version
        Safer from UI resize race conditions
        """
        try:
            if not self.running:
                return
            
            if self._updating:
                return
            
            if frame is None:
                return
            
            if not hasattr(frame, "shape") or len(frame.shape) < 3:
                return
            
            self._updating = True
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # Check if UI label exists
            if self.ui_label is None or self.ui_label.isHidden():
                return
            
            #  THROTTLING (like working version)
            now = time.time()
            if not hasattr(self, "_last_emit"):
                self._last_emit = 0
            if now - self._last_emit < (1.0 / 20.0):  # 20 FPS max
                return
            self._last_emit = now
            
            #  PRE-SCALE IN WORKER THREAD (key fix!)
            label_w = max(1, self.ui_label.width())
            label_h = max(1, self.ui_label.height())
            
            scaled_image = qt_image.scaled(
                label_w, 
                label_h,
                Qt.KeepAspectRatio,  # ← Match working version
                Qt.SmoothTransformation
            )
            
            # Emit already-scaled image
            try:
                self.change_pixmap_signal.emit(scaled_image)
            except Exception:
                pass
        
        except Exception as e:
            print("Exception in get_frames_from_backend():", e)
            traceback.print_exc()
        finally:
            self._updating = False

    def clear_violation_ui_label(self):
        """  Clear violation label reference"""
        try:
            if self.violation_ui_label is not None:
                self.violation_ui_label = None
                print(" Violation label cleared")
        except Exception as e:
            print(f"⚠️ Error clearing violation label: {e}")

    def get_violation_frames_from_backend(self, frame):
        """
         Violation frame callback with pre-scaling
        Prevents crashes on IP camera and video files
        """
        try:
            if not self.running:
                return
            
            # EOF detection
            if frame is None:
                try:
                    self.violation_pixmap_signal.emit(None)
                except:
                    pass
                return
            
            # Check violation label exists
            try:
                if self.violation_ui_label is None:
                    return
                
                _ = self.violation_ui_label.isVisible()
                
                if self.violation_ui_label.isHidden():
                    return
                
            except RuntimeError:
                print("⚠️ Violation label deleted")
                self.violation_ui_label = None
                return
            
            # Validate frame
            if not hasattr(frame, "shape") or len(frame.shape) < 3:
                return
            
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # Throttle to 20 FPS (same as monitor)
            now = time.time()
            if now - self._last_violation_emit < (1.0 / 20.0):
                return
            self._last_violation_emit = now
            
            #  KEY FIX: Pre-scale in worker thread
            label_w = max(1, self.violation_ui_label.width())
            label_h = max(1, self.violation_ui_label.height())
            
            scaled_image = qt_image.scaled(
                label_w,
                label_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # Emit pre-scaled image
            try:
                self.violation_pixmap_signal.emit(scaled_image)
            except RuntimeError:
                print("⚠️ Violation signal emit failed")
                self.violation_ui_label = None
            except Exception as e:
                print(f"⚠️ Violation frame emit error: {e}")
        
        except Exception as e:
            print(f"❌ Exception in get_violation_frames_from_backend(): {e}")

    def set_mode(self, mode):
        """Set detection/tracking mode"""
        try:
            if self.backendUI:
                try:
                    self.backendUI.setMode(mode)
                    self.log_signal.emit(f"Mode set to {mode}")
                except Exception as e:
                    print(f"Failed to set mode: {e}")
            else:

                self._pending_mode = mode
        except Exception:
            pass

    def set_save_enabled(self, enabled: bool):
        """Enable/disable saving"""
        if hasattr(self.backendUI, "backend") and hasattr(self.backendUI.backend, "Detector"):
            self.backendUI.backend.set_save_enabled(enabled)
        else:
            self.append_log("❌ Backend or Detector not initialized yet")
    
    def stop(self):
        """Stop the thread and the backend safely."""
        self.running = False

        # Disconnect signals on the Qt side
        try:
            self.change_pixmap_signal.disconnect()
        except Exception:
            pass
        try:
            self.violation_pixmap_signal.disconnect()
        except Exception:
            pass
        try:
            self.log_signal.disconnect()
        except Exception:
            pass

        # Ask backend to stop
        try:
            if self.backendUI:
                try:
                    self.backendUI.stop_all_modes()
                except Exception:
                    pass
                if hasattr(self.backendUI, "stop"):
                    try:
                        self.backendUI.stop()
                    except Exception:
                        pass
        except Exception:
            pass

class LoginScreen(QWidget):
    def __init__(self, auth_manager, on_login_success, on_go_to_signup):
        super().__init__()
        self.auth_manager = auth_manager
        self.on_login_success = on_login_success
        self.on_go_to_signup = on_go_to_signup
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(400)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(40, 40, 40, 40)

        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap("PPE.png")
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(logo_label)

        title = QLabel("Login")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email")
        self.email_input.setStyleSheet(f"background-color: {BACKGROUND_COLOR}; color: {TEXT_COLOR}; padding: 10px; border: 1px solid #374151; border-radius: 6px;")
        card_layout.addWidget(self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(f"background-color: {BACKGROUND_COLOR}; color: {TEXT_COLOR}; padding: 10px; border: 1px solid #374151; border-radius: 6px;")
        card_layout.addWidget(self.password_input)

        self.login_btn = QPushButton("Login")
        self.login_btn.setObjectName("PrimaryButton")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.login_btn.clicked.connect(self.handle_login)
        card_layout.addWidget(self.login_btn)

        self.signup_link = QPushButton("Don't have an account? Sign up")
        self.signup_link.setObjectName("TabButton")
        self.signup_link.setCursor(Qt.PointingHandCursor)
        self.signup_link.setIcon(self.style().standardIcon(QStyle.SP_DialogHelpButton))
        self.signup_link.clicked.connect(self.on_go_to_signup)
        card_layout.addWidget(self.signup_link)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {DANGER_COLOR};")
        self.error_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.error_label)

        layout.addWidget(card)

    def handle_login(self):
        email = self.email_input.text()
        password = self.password_input.text()
        
        if not email or not password:
            self.error_label.setText("Please fill in all fields")
            return

        self.login_btn.setText("Logging in...")
        self.login_btn.setEnabled(False)
        QApplication.processEvents()

        result = self.auth_manager.login(email, password)
        
        self.login_btn.setText("Login")
        self.login_btn.setEnabled(True)

        if result["success"]:
            self.on_login_success()
        else:
            self.error_label.setText(result["error"])

class SignupScreen(QWidget):
    def __init__(self, auth_manager, on_signup_success, on_go_to_login):
        super().__init__()
        self.auth_manager = auth_manager
        self.on_signup_success = on_signup_success
        self.on_go_to_login = on_go_to_login
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(400)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(40, 40, 40, 40)

        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap("PPE.png")
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(logo_label)

        title = QLabel("Sign Up")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email")
        self.email_input.setStyleSheet(f"background-color: {BACKGROUND_COLOR}; color: {TEXT_COLOR}; padding: 10px; border: 1px solid #374151; border-radius: 6px;")
        card_layout.addWidget(self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(f"background-color: {BACKGROUND_COLOR}; color: {TEXT_COLOR}; padding: 10px; border: 1px solid #374151; border-radius: 6px;")
        card_layout.addWidget(self.password_input)

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Confirm Password")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setStyleSheet(f"background-color: {BACKGROUND_COLOR}; color: {TEXT_COLOR}; padding: 10px; border: 1px solid #374151; border-radius: 6px;")
        card_layout.addWidget(self.confirm_password_input)

        self.signup_btn = QPushButton("Sign Up")
        self.signup_btn.setObjectName("PrimaryButton")
        self.signup_btn.setCursor(Qt.PointingHandCursor)
        self.signup_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.signup_btn.clicked.connect(self.handle_signup)
        card_layout.addWidget(self.signup_btn)

        self.login_link = QPushButton("Already have an account? Login")
        self.login_link.setObjectName("TabButton")
        self.login_link.setCursor(Qt.PointingHandCursor)
        self.login_link.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.login_link.clicked.connect(self.on_go_to_login)
        card_layout.addWidget(self.login_link)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {DANGER_COLOR};")
        self.error_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.error_label)

        layout.addWidget(card)

    def handle_signup(self):
        email = self.email_input.text()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        
        if not email or not password or not confirm_password:
            self.error_label.setText("Please fill in all fields")
            return

        if password != confirm_password:
            self.error_label.setText("Passwords do not match")
            return

        self.signup_btn.setText("Signing up...")
        self.signup_btn.setEnabled(False)
        QApplication.processEvents()

        result = self.auth_manager.signup(email, password)
        
        self.signup_btn.setText("Sign Up")
        self.signup_btn.setEnabled(True)

        if result["success"]:
            self.on_signup_success()
        else:
            self.error_label.setText(result["error"])

class ConnectionScreen(QWidget):
    def __init__(self, switch_callback):
        super().__init__()
        self.switch_callback = switch_callback
        self.model_path = "epoch31.pt"   # default model
        self.selected_source = "webcam"  # default
        self.video_path = None
        self.ip_url = None
        self.resize(1400, 900)
        self.setMinimumSize(1280, 800)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # --- Main Card ---
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(550)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(35, 35, 35, 35)

        # Icon
        logo_label = QLabel()
        logo_pixmap = QPixmap("PPE.png")
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(logo_label)

        # Title
        title = QLabel("PPE Safety Monitor")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Connect to a camera source to begin monitoring\nworkplace safety")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        # Tabs
        tabs_layout = QHBoxLayout()
        self.btn_upload = QPushButton("Upload Video")
        self.btn_upload.setObjectName("TabButton")
        self.btn_upload.setCursor(Qt.PointingHandCursor)
        self.btn_upload.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_upload.clicked.connect(lambda: self.set_tab("video"))

        self.btn_webcam = QPushButton("System Webcam")
        self.btn_webcam.setObjectName("TabButton")
        self.btn_webcam.setCursor(Qt.PointingHandCursor)
        self.btn_webcam.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.btn_webcam.clicked.connect(lambda: self.set_tab("webcam"))

        self.btn_ipcam = QPushButton("IP Camera")
        self.btn_ipcam.setObjectName("TabButton")
        self.btn_ipcam.setCursor(Qt.PointingHandCursor)
        self.btn_ipcam.setIcon(self.style().standardIcon(QStyle.SP_DriveNetIcon))
        self.btn_ipcam.clicked.connect(lambda: self.set_tab("ip_camera"))

        tabs_layout.addWidget(self.btn_upload)
        tabs_layout.addWidget(self.btn_webcam)
        tabs_layout.addWidget(self.btn_ipcam)
        card_layout.addLayout(tabs_layout)

        # Input Area
        self.input_area = QVBoxLayout()
        card_layout.addLayout(self.input_area)
        # --- Model Selection ---
        model_label = QLabel("Select Model")
        model_label.setObjectName("Subtitle")
        card_layout.addWidget(model_label)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "Default Model (epoch31.pt)",
            "Custom Model..."
        ])
        self.model_combo.currentIndexChanged.connect(self.select_custom_model)
        card_layout.addWidget(self.model_combo)
        
        # --- Tracking Model Selection ---
        tracking_label = QLabel("Select Tracking Model")
        tracking_label.setObjectName("Subtitle")
        card_layout.addWidget(tracking_label)

        self.tracking_combo = QComboBox()
        self.tracking_combo.addItems([
            "Default Tracking (OSNet)",
            "Custom Tracking Model..."
        ])
        self.tracking_combo.currentIndexChanged.connect(self.select_custom_tracking)
        card_layout.addWidget(self.tracking_combo)

        # Initialize tracking path
        self.tracking_path = "osnet_ain_x1_0_market1501_256x128_amsgrad_ep100_lr0.0015_coslr_b64_fb10_softmax_labsmth_flip_jitter.pth"
        # Create Gpu Checkboxes
        gpu_container = QFrame()
        gpu_container.setStyleSheet(f"background-color: {CARD_COLOR}; border-radius: 4px; padding: 4px;")
        gpu_layout = QVBoxLayout(gpu_container)

        # Check CUDA availability
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_status = f"✅ GPU Available: {gpu_name}"
            gpu_color = "#10b981"
        else:
            gpu_status = " ⚠️ No GPU detected - CPU will be used"
            gpu_color = "#F59E0B"

        gpu_status_label = QLabel(gpu_status)
        gpu_status_label.setStyleSheet(f"color: {gpu_color}; font-size: 12px; padding: 5px;font-weight: bold;")
        gpu_layout.addWidget(gpu_status_label)

        self.gpu_checkbox = QCheckBox("Use GPU (CUDA) if available")
        self.gpu_checkbox.setChecked(cuda_available)  # Auto-enable if available
        self.gpu_checkbox.setEnabled(cuda_available)  # Disable if no GPU

        card_layout.addWidget(gpu_container,)
        gpu_layout.addWidget(self.gpu_checkbox)

        # Initialize GPU preference
        self.use_gpu = cuda_available




        # Activate Button
        self.btn_activate = QPushButton("Activate Camera")
        self.btn_activate.setObjectName("PrimaryButton")
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_activate.clicked.connect(self.handle_activate)
        card_layout.addWidget(self.btn_activate)

        layout.addWidget(card)

        # Initialize default tab
        self.set_tab("webcam")

    def set_tab(self, mode):
        self.selected_source = mode

        # Update Tab Styles
        self.btn_upload.setProperty("active", mode == "video")
        self.btn_webcam.setProperty("active", mode == "webcam")
        self.btn_ipcam.setProperty("active", mode == "ip_camera")
        for btn in [self.btn_upload, self.btn_webcam, self.btn_ipcam]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Clear Input Area
        for i in reversed(range(self.input_area.count())):
            widget = self.input_area.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        if mode == "webcam":
            lbl = QLabel("Select Camera")
            lbl.setObjectName("Subtitle")
            self.input_area.addWidget(lbl)

            combo = QComboBox()
            combo.addItems(["Built-in Webcam", "External USB Camera"])
            self.input_area.addWidget(combo)
            self.btn_activate.setText("Activate Camera")

        elif mode == "video":
            lbl = QLabel("Select Video File")
            lbl.setObjectName("Subtitle")
            self.input_area.addWidget(lbl)

            self.file_btn = QPushButton("Browse File...")
            self.file_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
            self.file_btn.clicked.connect(self.browse_file)
            self.input_area.addWidget(self.file_btn)
            self.btn_activate.setText("Load Video")

        elif mode == "ip_camera":
            lbl = QLabel("Enter IP Camera URL")
            lbl.setObjectName("Subtitle")
            self.input_area.addWidget(lbl)
        
            # Container frame for styling
            input_container = QFrame()
            input_container.setStyleSheet("background-color: black; border-radius: 8px;")
            container_layout = QVBoxLayout(input_container)
            container_layout.setContentsMargins(5, 5, 5, 5)
        
            # IP input field
            self.ip_input = QLineEdit()
            self.ip_input.setPlaceholderText("e.g., http://192.168.1.100:8080/video")
            self.ip_input.setStyleSheet("color: white; background-color: black; border: 1px solid #374151; padding: 5px;")
            container_layout.addWidget(self.ip_input)
        
            self.input_area.addWidget(input_container)
            self.btn_activate.setText("Activate IP Camera")

    def browse_file(self):
        default_dir = os.path.join(os.getcwd(), "Saved_Detections")
        if not os.path.exists(default_dir):
            default_dir = os.getcwd()
            
        fname, _ = QFileDialog.getOpenFileName(self, 'Open Video', default_dir, "Video files (*.mp4 *.avi)")
        if fname:
            self.video_path = fname
            self.file_btn.setText(fname.split('/')[-1])
    
    def handle_activate(self):
        source = None
        if self.selected_source == "video":
            if not self.video_path:
                return
            source = self.video_path
        elif self.selected_source == "webcam":
            source = 0  # Default webcam
        elif self.selected_source == "ip_camera":
            ip_url = self.ip_input.text().strip()
            if not ip_url:
                return
            source = ip_url  # IP camera URL
        
        # Get GPU preference from checkbox
        self.use_gpu = self.gpu_checkbox.isChecked()
        
        #self.switch_callback(source)
        self.switch_callback(source, self.model_path,self.tracking_path,self.use_gpu)

    def select_custom_model(self, index):
        default_model_dir = os.path.join(os.getcwd(), "yolo_models")
        if not os.path.exists(default_model_dir):
            default_model_dir = os.getcwd()

        if index == 1:  # Custom Model
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select YOLO Model",
                default_model_dir,

                "YOLO Model (*.pt)"
            )
            if file_path:
                self.model_path = file_path
                self.model_combo.setItemText(1, f"Custom: {os.path.basename(file_path)}")
            else:
                # user canceled → revert to default
                self.model_combo.setCurrentIndex(0)
                self.model_path = "epoch31.pt"
        else:
            self.model_path = "epoch31.pt"

    def select_custom_tracking(self, index):
        default_tracking_dir = os.path.join(os.getcwd(), "tracking_models")
        if not os.path.exists(default_tracking_dir):
            default_tracking_dir = os.getcwd()

        DEFAULT_TRACKING_MODEL = (
            "tracking_models\\osnet_ain_x1_0_market1501_256x128_amsgrad_ep100_lr0.0015_coslr_b64_fb10_softmax_labsmth_flip_jitter.pth"
        )

        if index == 1:  # Custom Tracking Model
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Tracking Model",
                default_tracking_dir,
                "Tracking Model (*.pth *.pt)"
            )

            if file_path:
                self.tracking_path = file_path
                self.tracking_combo.setItemText(
                    1, f"Custom: {os.path.basename(file_path)}"
                )
            else:
                # User canceled → revert to default
                self.tracking_combo.setCurrentIndex(0)
                self.tracking_path = DEFAULT_TRACKING_MODEL
        else:
            self.tracking_path = DEFAULT_TRACKING_MODEL

class BaseMonitorScreen(QWidget):
    
    def __init__(self, screen_type="monitor",log_callback=None):
        # screen_type: "monitor" or "violation"
        super().__init__()
        self.log_callback=log_callback
        self.screen_type = screen_type
        
        # main stylesheet

        self.setStyleSheet(f"""
        
        QWidget {{
            background-color: {BACKGROUND_COLOR};
            color: {TEXT_COLOR};
        }}
        QFrame#HeaderFrame {{
            background-color: {CARD_COLOR};
            border: 1px solid #374151;
            border-radius: 8px;
            margin-bottom: 10px;
        }}
        QLabel#Title {{
            color: {TEXT_COLOR};
            font-size: 24px;
            font-weight: bold;
        }}
        QFrame#VideoContainer {{
            background-color: {CARD_COLOR};
            border: 2px solid #374151;
            border-radius: 8px;
        }}
        QPushButton#DangerButton {{
            background-color: #DC2626;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: bold;
        }}
        QPushButton#DangerButton:hover {{
            background-color: #B91C1C;
        }}
        QScrollBar:vertical {{
            background-color: {CARD_COLOR};
            width: 12px;
            border-radius: 6px;
        }}
        QScrollBar::handle:vertical {{
            background-color: #374151;
            border-radius: 6px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: #4b5563;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QPushButton {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: #0284c7;
        }}
        QPushButton:disabled {{
            background-color: #374151;
            color: #6b7280;
        }}
        """)
        
        # Video frame protection
        self._frame_update_lock = threading.Lock()
        self._is_resizing = False
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_finished)
        self._pending_frame = None
        self._last_frame_time = 0
        self._min_frame_interval = 1.0 / 30.0  # 30 FPS max
        
        # UI components (will be set by child classes)
        self.video_frame = None
        self.log_panel = None
        self.class_selection_panel = None
        self.checkboxes = {}
        self.status_badge = None
        self.btn_disconnect = None
        
        # Button styles (common)
        self.active_style = (
            "background-color: #DC2626; color: white; padding: 12px 24px; "
            "border-radius: 6px; font-weight: bold;"
        )
        self.default_style = (
            f"background-color: {PRIMARY_COLOR}; color: white; padding: 12px 24px; "
            "border-radius: 6px; font-weight: bold;"
        )
        self.default_card_style = (
            f"background-color: {CARD_COLOR}; color: white; "
            "border: 1px solid #374151; padding: 12px 24px; "
            "border-radius: 6px; font-weight: bold;"
        )
    
    def resizeEvent(self, event):
        """Detect window resize and pause frame updates"""
        self._is_resizing = True
        
        if self._resize_timer.isActive():
            self._resize_timer.stop()
        self._resize_timer.start(150)  # Wait 150ms after last resize
        
        super().resizeEvent(event)
    
    def _on_resize_finished(self):
        """Called when resize is complete"""
        self._is_resizing = False
        
        if self._pending_frame is not None:
            try:
                self._do_update_frame(self._pending_frame)
            except Exception as e:
                self.append_log(f"⚠️ Error updating pending frame: {e}")
            finally:
                self._pending_frame = None
    
    def update_video_frame(self, qt_img):
        """
        Thread-safe frame update with resize protection.
        Can be called from both MonitorScreen and ViolationScreen.
        """
        try:
            # Skip if resizing
            if self._is_resizing:
                if self._pending_frame is None:
                    self._pending_frame = qt_img
                return
            
            # Throttle frame rate
            current_time = time.time()
            if current_time - self._last_frame_time < self._min_frame_interval:
                return
            
            self._last_frame_time = current_time
            
            # Try to acquire lock (non-blocking)
            if not self._frame_update_lock.acquire(blocking=False):
                return
            
            try:
                self._do_update_frame(qt_img)
            finally:
                self._frame_update_lock.release()
        
        except Exception as e:
            print(f"❌ Error in update_video_frame: {e}")
    
    def _do_update_frame(self, qt_img):
        """Protected: Actual frame update with validation"""
        try:
            if not hasattr(self, 'video_frame') or self.video_frame is None:
                return
            
            try:
                if sip.isdeleted(self.video_frame):
                    self.video_frame = None
                    return
            except RuntimeError:
                self.video_frame = None
                return
            
            if not self.video_frame.isVisible():
                return
            
            try:
                label_width = self.video_frame.width()
                label_height = self.video_frame.height()
            except RuntimeError:
                return
            
            if label_width < 50 or label_height < 50:
                return
            
            if self._is_resizing:
                return
            
            try:
                scaled = qt_img.scaled(
                    label_width,
                    label_height,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            except Exception as e:
                print(f"⚠️ Scaling failed: {e}")
                return
            
            if self._is_resizing:
                return
            
            try:
                if not sip.isdeleted(self.video_frame):
                    self.video_frame.setPixmap(QPixmap.fromImage(scaled))
            except RuntimeError:
                self.video_frame = None
        
        except Exception as e:
           print(f"❌ Error in _do_update_frame: {e}")
    
    def create_main_layout(self):
        """
        Create the standard 3-column layout:
        [Left Sidebar] [Center Content] [Right Sidebar]
        """
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        
        # LEFT SIDEBAR
        left_sidebar = self.create_left_sidebar()
        main_layout.addWidget(left_sidebar)
        
        # CENTER CONTENT
        center_widget = self.create_center_content()
        main_layout.addWidget(center_widget, stretch=3)
        
        # RIGHT SIDEBAR
        right_sidebar = self.create_right_sidebar()
        main_layout.addWidget(right_sidebar, stretch=1)
    
    def create_left_sidebar(self):
        """Create left sidebar with class selection panel"""
        left_sidebar = QFrame()
        left_sidebar.setStyleSheet(
            f"background-color: {CARD_COLOR}; border-right: 2px solid #374151;"
        )
        left_sidebar.setFixedWidth(250)
        
        sidebar_layout = QVBoxLayout(left_sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Class selection panel (will be customized by child)
        panel_title = "Detection Classes" if self.screen_type == "monitor" else "Violation Classes"
        panel_subtitle = "Select objects to track" if self.screen_type == "monitor" else "Select required PPE"
        
        self.class_selection_panel = ClassSelectionPanel(
            title=panel_title,
            subtitle=panel_subtitle
        )
        
        sidebar_layout.addWidget(self.class_selection_panel)
        
        # Child classes can add buttons here
        self.add_left_sidebar_buttons(sidebar_layout)
        
        return left_sidebar
    
    def create_center_content(self):
        """Create center content with header, video, and controls"""
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(10, 10, 10, 10)
        center_layout.setSpacing(10)
        
        # HEADER
        header_frame = self.create_header()
        center_layout.addWidget(header_frame)
        
        # VIDEO CONTAINER
        video_container = self.create_video_container()
        center_layout.addWidget(video_container, stretch=1)
        
        # CONTROL BUTTONS
        controls_layout = self.create_control_buttons()
        center_layout.addLayout(controls_layout)
        
        return center_widget
    
    def create_header(self):
        """Create header with title, status badge, and disconnect button"""
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        # Title
        if self.screen_type == "monitor":
            title_text = "PPE Safety Monitor"
            status_text = "Live"
            status_color = "#10b981"
            disconnect_text = "Disconnect"
        else:  # violation
            title_text = "PPE Violation Monitor"
            status_text = "Idle"
            status_color = "#F59E0B"
            disconnect_text = "Stop Violation Checking"
        
        title = QLabel(title_text)

        title.setObjectName("Title")
        title.setStyleSheet('font-size: 24px;font-weight: bold;background-color:transparent')
        
        # Status badge
        self.status_badge = QLabel(status_text)
        self.status_badge.setStyleSheet(
            f"color: {status_color}; font-weight: bold; "
            f"background-color: rgba({self._hex_to_rgba(status_color, 0.1)}); "
            "padding: 5px 10px; border-radius: 12px;"
        )
        
        # Disconnect button
        self.btn_disconnect = QPushButton(disconnect_text)
        self.btn_disconnect.setIcon(self.style().standardIcon(QStyle.SP_BrowserStop))
        self.btn_disconnect.setObjectName("DangerButton")
        self.btn_disconnect.setCursor(Qt.PointingHandCursor)
        self.btn_disconnect.clicked.connect(self.handle_disconnect)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.status_badge)
        header_layout.addWidget(self.btn_disconnect)
        
        return header_frame
    
    def create_video_container(self):
        """Create video display container"""
        video_container = QFrame()
        video_container.setObjectName("VideoContainer")
        video_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0,0)
        video_layout.setSpacing(0)
        
        self.video_frame = QLabel("Initializing Video Stream...")
        self.video_frame.setAlignment(Qt.AlignCenter)
        self.video_frame.setStyleSheet("color: #6B7280; font-size: 18px; background-color: transparent;")
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        #self.video_frame.setMinimumSize(640, 640)
        
       
        video_layout.addWidget(self.video_frame, stretch=1)
        
        return video_container
    
    def create_control_buttons(self):
        """Override in child classes to create specific control buttons"""
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)
        return controls_layout
    
    def create_right_sidebar(self):
        """Create right sidebar with log panel"""
        sidebar = QFrame()
        sidebar.setStyleSheet(
            f"background-color: {CARD_COLOR}; border-left: 2px solid #374151;"
        )
        sidebar.setFixedWidth(320)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        
        log_title = "System Logs" if self.screen_type == "monitor" else "Violation Logs"
        self.log_panel = LogPanel(title=log_title)
        sidebar_layout.addWidget(self.log_panel)
        
        return sidebar
    
    def append_log(self, message, log_type="INFO"):
        """Add log entry using shared panel"""
        if self.log_panel:
            self.log_panel.append_log(message, log_type)
    
    def clear_logs(self):
        """Clear logs using shared panel"""
        if self.log_panel:
            self.log_panel.clear_logs()
    
    def _hex_to_rgba(self, hex_color, alpha):
        """Convert hex color to rgba string"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"{r}, {g}, {b}, {alpha}"
    
    def center_on_screen(self):
        """Center the window on screen"""
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        center_point = screen.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())
    
    def get_selected_classes(self, return_type="name"):
        """Get selected classes from the class selection panel"""
        if not self.class_selection_panel:
            return []
        
        selected_names = self.class_selection_panel.get_selected_classes()
        
        if return_type.lower() == "name":
            return selected_names
        
        # If ID needed, child class should override with detector reference
        return selected_names
    
    def handle_disconnect(self):
        """Override in child classes"""
        raise NotImplementedError("Child class must implement handle_disconnect()")

class MonitorScreen(BaseMonitorScreen):
    def __init__(self, switch_callback):
        super().__init__(screen_type="monitor")
        self.resize(1400, 800)
        self.setMinimumSize(1280, 720)
        
        self.switch_callback = switch_callback
        self.thread = None
        self.is_detection_running = False
        self.is_saving = False
        self.violation_window = None
        
        # Additional monitor-specific attributes
        self.selected_class_handler = None
        
        # Initialize UI using base class
        self.create_main_layout()  #  From base class
        
        print(" MonitorScreen initialized with base class")
    
    def add_left_sidebar_buttons(self, layout):
        """No extra buttons needed for MonitorScreen"""
        pass
    
    def create_control_buttons(self):
        """Create monitor-specific control buttons"""
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)
        
        
        # Detection button
        self.btn_detect = QPushButton("Start Detection")
        self.btn_detect.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_detect.setCursor(Qt.PointingHandCursor)
        self.btn_detect.setStyleSheet(self.default_style)
        self.btn_detect.setFixedHeight(45)
        self.btn_detect.clicked.connect(lambda: self.handle_mode("detection"))
        
        # Tracking button
        self.btn_track = QPushButton("Start Tracking")
        self.btn_track.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.btn_track.setCursor(Qt.PointingHandCursor)
        self.btn_track.setStyleSheet(self.default_card_style)
        self.btn_track.setFixedHeight(45)
        self.btn_track.clicked.connect(lambda: self.handle_mode("tracking"))
        
        # Full Monitor button
        self.btn_full = QPushButton("Full Monitor")
        self.btn_full.setIcon(self.style().standardIcon(QStyle.SP_DesktopIcon))
        self.btn_full.setCursor(Qt.PointingHandCursor)
        self.btn_full.setStyleSheet(self.default_style)
        self.btn_full.setFixedHeight(45)
        self.btn_full.clicked.connect(lambda: self.handle_mode("full_monitor"))
        
        # Violation Screen button
        self.btn_violation = QPushButton("Violation Screen")
        self.btn_violation.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.btn_violation.setCursor(Qt.PointingHandCursor)
        self.btn_violation.setStyleSheet(self.default_style)
        self.btn_violation.setFixedHeight(45)
        
        self.btn_violation.clicked.connect(self.open_violation_screen)
        
        # Save button
        self.btn_save = QPushButton("Start Recording")
        self.btn_save.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(self.default_card_style)
        self.btn_save.setFixedHeight(45)
        self.btn_save.clicked.connect(self.toggle_save_detections)
        
        controls_layout.addWidget(self.btn_detect)
        controls_layout.addWidget(self.btn_track)
        controls_layout.addWidget(self.btn_full)
        controls_layout.addStretch()
        controls_layout.addWidget(self.btn_violation)
        controls_layout.addWidget(self.btn_save)
        
        return controls_layout
    
    def handle_disconnect(self):
        """Stop stream and return to connection screen"""
        #  Warn user if violation screen is active
        if hasattr(self, 'violation_window') and self.violation_window is not None:
            try:
                if not sip.isdeleted(self.violation_window) and self.violation_window.violation_active:
                    msg_box = QMessageBox(self)
                    msg_box.setIcon(QMessageBox.Question)
                    msg_box.setWindowTitle("Violation Detection Active")
                    msg_box.setText(
                        "Violation detection is currently running.\n\n"
                        "Disconnecting will close the Violation Monitor.\n\n"
                        "Continue?"
                    )
                    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

                    # Apply stylesheet
                    msg_box.setStyleSheet(f"""
                        QMessageBox {{
                            background-color: {CARD_COLOR};
                            color: {TEXT_COLOR};
                        }}
                        QMessageBox QLabel {{
                            color: {TEXT_COLOR};
                            font-size: 13px;
                        }}
                        QMessageBox QPushButton {{
                            background-color: {PRIMARY_COLOR};
                            color: white;
                            border: none;
                            padding: 10px 24px;
                            border-radius: 4px;
                            font-weight: bold;
                            min-width: 100px;
                            min-height: 38px;
                        }}
                        QMessageBox QPushButton:hover {{
                            background-color: #0284c7;
                        }}
                    """)

                    if msg_box.exec_() == QMessageBox.No:
                        return

                # Close violation screen
                if not sip.isdeleted(self.violation_window):
                    self.violation_window.close()
                    self.append_log("🔴 Violation screen closed", log_type="INFO")
            except RuntimeError:
                pass
            finally:
                self.violation_window = None

        self.stop_stream()
        self.reset_buttons_styles()
    
    def show_full_monitor_confirmation(self):
        """Show confirmation dialog for Full Monitor mode"""
        dialog = QDialog(self)
        dialog.setWindowTitle("⚡ Full Monitor Mode")
        dialog.setFixedWidth(480)

        # Apply stylesheet
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {CARD_COLOR};
                border: 1px solid #374151;
                border-radius: 8px;
            }}
            QLabel {{
                color: {TEXT_COLOR};
                font-size: 14px;
            }}
            QPushButton {{
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 140px;
                min-height: 42px;
                font-size: 14px;
            }}
            QPushButton#StartButton {{
                background-color: {PRIMARY_COLOR};
                color: white;
            }}
            QPushButton#StartButton:hover {{
                background-color: #0284c7;
            }}
            QPushButton#CancelButton {{
                background-color: transparent;
                border: 1px solid #374151;
                color: {SECONDARY_TEXT};
            }}
            QPushButton#CancelButton:hover {{
                background-color: #374151;
                color: {TEXT_COLOR};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # Title
        title = QLabel("⚡ Full Monitor Mode")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Full Monitor mode will automatically:\n\n"
            " Start Detection + Tracking\n"
            " Begin Video Recording\n"
            " Open Violation Monitor\n\n"
            "This mode is designed for comprehensive safety monitoring "
            "with automatic violation detection and recording."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {TEXT_COLOR}; padding: 15px; "
            "background-color: rgba(14, 165, 233, 0.1); "
            "border-left: 3px solid #0ea5e9; border-radius: 4px; font-size: 13px; line-height: 1.6;"
        )
        layout.addWidget(desc)

        # Warning box
        warning = QLabel(
            "⚠️ Note: Make sure you have:\n"
            "• Sufficient storage space for recordings\n"
            "• Required PPE classes selected\n"
            "• Email alerts configured (optional)"
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            f"color: {SECONDARY_TEXT}; padding: 12px; "
            "background-color: rgba(245, 158, 11, 0.1); "
            "border-left: 3px solid #F59E0B; border-radius: 4px; font-size: 12px;"
        )
        layout.addWidget(warning)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("CancelButton")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        start_btn = QPushButton("⚡ Start Full Monitor")
        start_btn.setObjectName("StartButton")
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(start_btn)

        layout.addLayout(btn_layout)

        # Show dialog
        result = dialog.exec_()
        return result == QDialog.Accepted

    def update_frames_on_monitor_screen(self, qt_img):
        """MonitorScreen frame update - delegates to base class"""
        self.update_video_frame(qt_img)  #  From base class
    
    def get_selected_classes_ids(self, return_type="id"):
        """ UPDATED: Use panel's built-in methods"""
        if return_type.lower() == "name":
            return self.class_selection_panel.get_selected_classes()
        
        #  Use built-in method that handles IDs
        return self.class_selection_panel.get_selected_class_ids()

    def start_stream(self, source, model_path, tracking_path, use_gpu):
        if self.thread:
            self.disconnect_connection()
            self.video_frame.setText("⏳ Connecting to camera...")
            self.video_frame.setStyleSheet("color: #F59E0B; font-size: 18px; background-color: black;")
            QApplication.processEvents()
        
        self.thread = VideoThread(source=source, model_path=model_path,tracking_path=tracking_path,use_gpu=use_gpu, ui_label=self.video_frame,log_callback=self.log_panel.append_log)
        self.thread.change_pixmap_signal.connect(self.update_frames_on_monitor_screen)
        self.thread.log_signal.connect(self.append_log)
        self.thread.model_loaded_signal.connect(self.show_model_classes)
        self.thread.start()
        device_str = "GPU" if use_gpu else "CPU"
        #source_type = "Webcam" if isinstance(self.source, int) else ("IP Camera" if "http" in str(self.source).lower() or "rtsp" in str(self.source).lower()else "Video File")
        self.append_log(f"Camera Connected: {source} ({device_str})",log_type="INFO")
    
    def stop_stream(self):
        """Stop stream with error handling"""

        if hasattr(self, 'violation_window') and self.violation_window is not None:
            try:
                if not sip.isdeleted(self.violation_window):
                    self.violation_window.close()
            except RuntimeError:
                pass
            finally:
                self.violation_window = None
        
        if self.thread:
            try:
                if hasattr(self.thread, 'backendUI') and self.thread.backendUI:
                    if hasattr(self.thread.backendUI, 'backend') and self.thread.backendUI.backend:
                        self.thread.backendUI.backend.set_save_options(False)
                        self.append_log("🔌 Camera Disconnected. Saving Stopped.")
            except Exception as e:
                print(f"⚠️ Error stopping save options: {e}")
            
            try:
                self.thread.running = False
                self.thread.wait()
            except Exception as e:
                print(f"⚠️ Error stopping thread: {e}")
            
            self.thread = None
            # ✅ FIX: Reset detection flag
            self.is_detection_running = False
            self.switch_callback()
            self.append_log("🔌 Camera Disconnected", log_type="INFO")
    
    def show_model_classes(self, class_names):
        """ UPDATED: Use merged ClassSelectionPanel with auto-sync"""

        # Get backend detector
        backend_detector = getattr(self.thread.backendUI.backend, "Detector", None)

        if backend_detector:
            #  Link backend to panel BEFORE populating
            self.class_selection_panel.set_backend_detector(backend_detector)
            print(" Backend detector linked to ClassSelectionPanel")
        else:
           print("⚠️ Backend detector not ready yet")

        #  Populate classes (will auto-sync to backend if linked)
        self.class_selection_panel.populate_classes(
            class_names=class_names,
            default_checked=["person"]
        )

        # Keep checkboxes reference for backward compatibility
        self.checkboxes = self.class_selection_panel.checkboxes
        
        self.append_log(f"Model Classes Loaded: {len(class_names)} Classes")

    def handle_mode(self, mode):
        """
        Handles starting/stopping Detection, Tracking, Full Monitor.
        UPDATED: Full Monitor shows confirmation and auto-starts recording + violation screen
        """
        full_active = self.btn_full.styleSheet() == self.active_style
        detect_active = self.btn_detect.styleSheet() == self.active_style
        track_active = self.btn_track.styleSheet() == self.active_style

        is_currently_recording = self.is_saving

        if mode == "detection":
            if full_active:
                return

            if detect_active:
                if track_active:
                    self.append_log("⚠️ Cannot stop detection while tracking is active", log_type="INFO")
                    return

                self.btn_detect.setStyleSheet(self.default_style)
                self.is_detection_running = False
                self.thread.set_mode("idle")
                self.append_log("🛑 Detection stopped.", log_type="INFO")
            else:
                self.btn_detect.setStyleSheet(self.active_style)
                self.btn_detect.setEnabled(True)
                self.btn_track.setEnabled(True)
                self.btn_full.setEnabled(True)
                self.thread.set_mode("detection")
                self.is_detection_running = True
                self.append_log("▶ Detection started.", log_type="INFO")

        elif mode == "tracking":
            if full_active:
                return

            if track_active:
                self.btn_track.setStyleSheet(self.default_card_style)

                if detect_active:
                    self.thread.set_mode("detection")
                    self.is_detection_running = True
                    self.append_log("🛑 Tracking stopped. Detection continues.", log_type="INFO")
                else:
                    self.thread.set_mode("idle")
                    self.is_detection_running = False
                    self.append_log("🛑 Tracking stopped.", log_type="INFO")
            else:
                self.btn_detect.setStyleSheet(self.active_style)
                self.btn_track.setStyleSheet(self.active_style)
                self.btn_full.setStyleSheet(self.default_style)
                self.btn_detect.setEnabled(True)
                self.btn_track.setEnabled(True)
                self.btn_full.setEnabled(True)
                self.thread.set_mode("tracking")
                self.is_detection_running = True
                self.append_log("◎ Detection + Tracking started.", log_type="INFO")

        elif mode == "full_monitor":
            if self.btn_full.styleSheet() == self.active_style:
                #  Stop Full Monitor
                self.btn_detect.setStyleSheet(self.default_style)
                self.btn_track.setStyleSheet(self.default_card_style)
                self.btn_full.setStyleSheet(self.default_style)
                self.btn_detect.setEnabled(True)
                self.btn_track.setEnabled(True)
                self.btn_full.setEnabled(True)
                self.thread.set_mode("idle")
                self.is_detection_running = False

                # Stop recording if it was auto-started
                if self.is_saving:
                    self.stop_saving()

                # Close violation screen if open
                if hasattr(self, 'violation_window') and self.violation_window is not None:
                    try:
                        if not sip.isdeleted(self.violation_window):
                            self.violation_window.close()
                    except RuntimeError:
                        pass
                    finally:
                        self.violation_window = None

                self.append_log("🛑 Full Monitoring stopped.", log_type="INFO")
            else:
                #  Show confirmation dialog before starting
                if not self.show_full_monitor_confirmation():
                    self.append_log("❌ Full Monitor cancelled", log_type="INFO")
                    return

                #  Start Full Monitor with recording
                self.btn_detect.setStyleSheet(self.active_style)
                self.btn_track.setStyleSheet(self.active_style)
                self.btn_full.setStyleSheet(self.active_style)
                self.btn_detect.setEnabled(False)
                self.btn_track.setEnabled(False)
                self.btn_full.setEnabled(True)
                self.thread.set_mode("tracking")
                self.is_detection_running = True



                # Create default save directory
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                save_root = f"recordings/Full_Monitor_{timestamp}"
                os.makedirs(save_root, exist_ok=True)

                self.is_saving = True
                self.btn_save.setText("Stop Recording")
                self.btn_save.setStyleSheet(self.active_style)
                self.btn_save.setEnabled(False)  # Disable manual control during Full Monitor

                # Start recording (both images and video)
                
                self.thread.backendUI.backend.set_save_options(True, "video", save_root)

                self.append_log("◉ Full Monitoring started.", log_type="INFO")
                self.append_log(f"💾 Auto-recording to: {os.path.abspath(save_root)}", log_type="INFO")

                #  Auto-open violation screen
                QTimer.singleShot(500, self.auto_open_violation_for_full_monitor)

        #  Preserve recording state (except for Full Monitor which handles it)
        if mode != "full_monitor" and is_currently_recording:
            self.is_saving = True
            self.btn_save.setText("Stop Recording")
            self.btn_save.setStyleSheet(self.active_style)

    def reset_buttons_styles(self):
        """Reset all buttons to default style and enable them."""
        self.btn_detect.setStyleSheet(self.default_style)
        self.btn_track.setStyleSheet(self.default_card_style)
        self.btn_full.setStyleSheet(self.default_style)
        self.btn_detect.setEnabled(True)
        self.btn_track.setEnabled(True)
        self.btn_full.setEnabled(True)

        self.is_saving = False
        self.btn_save.setText(" Start Recording")
        self.btn_save.setStyleSheet(self.default_card_style)
        self.btn_save.setEnabled(True)  #  Re-enable save button
    
    def disconnect_connection(self):
        #  Close violation screen first
        if hasattr(self, 'violation_window') and self.violation_window is not None:
            try:
                if not sip.isdeleted(self.violation_window):
                    self.violation_window.close()
            except RuntimeError:
                pass
            finally:
                self.violation_window = None

        if self.thread:
            if self.is_saving:
                self.stop_saving()

            try:
                self.thread.backendUI.stop_all_modes()
            except Exception as e:
                self.append_log("Error stopping backend modes:", e)

            try:
                self.thread.change_pixmap_signal.disconnect()
            except:
                pass

            try:
                self.thread.log_signal.disconnect()
            except:
                pass
            
            self.thread.running = False
            self.thread.wait()
            self.thread = None
        self.is_detection_running = False
        self.reset_buttons_styles()
    
    def toggle_save_detections(self):
        if not self.is_saving:
            self.save_options()
        else:
            self.stop_saving()
    
    def check_required_detection_classes_for_voilation(self):
        """
        Check if user selected required detection classes in Monitor Screen.
        Returns True if at least one required class is selected, else False.
        """
        required_classes = []
        selected_in_monitor = self.get_selected_classes_ids(return_type="name")
    
        missing_classes = [cls for cls in required_classes if cls not in selected_in_monitor]
        if missing_classes:
            self.append_log(f"⚠️ Cannot check violations! These classes are not selected in detection: {missing_classes}")
            self.append_log(f"⚠️ Please select these classes in Monitor Screen before checking violations: {missing_classes}")
            return False
    
        return True
    
    
    def _validate_camera_stability(self):
        """
        Validate camera is stable before opening violation screen
        Returns True if stable, False otherwise
        """
        try:
            # ✅ FIX: Check thread exists and is running
            if not self.thread or not self.thread.isRunning():
                print("❌ Thread not running")
                return False
            
            # ✅ FIX: Check backend is initialized
            if not hasattr(self.thread, 'backendUI') or self.thread.backendUI is None:
                print("❌ Backend not initialized")
                return False
            
            # ✅ FIX: Check detection flag AND verify backend mode
            if not self.is_detection_running:
                print("❌ Detection not running (flag check)")
                return False
            
            # ✅ NEW: Verify backend mode is actually active
            try:
                backend_mode = self.thread.backendUI.backend.Mode
                if backend_mode not in ["detection", "tracking"]:
                    self.append_log(f"❌ Backend mode is '{backend_mode}', not detection/tracking")
                    self.is_detection_running = False  # Fix desync
                    return False
            except Exception as e:
                print(f"❌ Cannot verify backend mode: {e}")
                return False
            
            # Check IP camera stability
            if isinstance(self.thread.source, str):
                if "http" in self.thread.source.lower() or "rtsp" in self.thread.source.lower():
                    if hasattr(self.thread.backendUI.backend, 'FPS_Counter'):
                        fps = self.thread.backendUI.backend.FPS_Counter.update()
                        if fps < 5:
                            self.append_log(f"⚠️ IP camera unstable (FPS: {fps:.1f})")
                            return False
            
            self.append_log("✅ Camera stability validated")
            return True
            
        except Exception as e:
            print(f"❌ Camera stability check failed: {e}")
            return False
    
    def open_violation_screen(self):
        """Network-resilient violation screen opening with retry logic"""
        try:
            if hasattr(self, "violation_window") and self.violation_window is not None:
                try:
                    if self.violation_window.isVisible():
                        self.append_log("⚠️ Violation screen already open")
                        self.violation_window.raise_()
                        self.violation_window.activateWindow()
                        return
                except RuntimeError:
                    self.violation_window = None
            
            if not self._validate_camera_stability():
                # Create the message box instance
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Information)
                msg_box.setWindowTitle("Camera Not Stable")
                msg_box.setText(
                    "Camera connection is unstable.\n\n"
                    "Please ensure:\n"
                    "• Detection is running\n"
                    "• Camera feed is stable\n"
                    "• Network connection is stable (for IP cameras)\n\n"
                    "Wait a few seconds and try again."
                )

                # Apply stylesheet
                msg_box.setStyleSheet(f"""
                    QMessageBox Icon {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                                      
                    QMessageBox {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                    QMessageBox QLabel {{
                        color: {TEXT_COLOR};
                        font-size: 15px;
                        background-color: {CARD_COLOR};
                    }}
                    QMessageBox QPushButton {{
                        background-color: {PRIMARY_COLOR};
                        color: white;
                        border: none;
                        padding: 8px 20px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 80px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #0284c7;
                    }}
                """)

                msg_box.exec_()
                return
            
            if not self.thread or not hasattr(self.thread, 'backendUI'):
                QMessageBox.warning(
                    self,
                    "Backend Not Ready",
                    "Please start detection first before opening Violation Monitor."
                )
                return
            
            if not hasattr(self.thread.backendUI, 'backend') or self.thread.backendUI.backend is None:
                QMessageBox.warning(
                    self,
                    "Backend Not Initialized",
                    "Backend is not properly initialized. Please restart detection."
                )
                return
            
            if not self.check_required_detection_classes_for_voilation():
                return
            
            progress = QProgressDialog("Initializing Violation Monitor...", None, 0, 0, self)
            progress.setWindowTitle("Opening Violation Monitor")
            progress.setWindowModality(Qt.NonModal)
            progress.setCancelButton(None)
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()
            
            try:
                self.violation_window = ViolationScreen(
                    detector=self.thread.backendUI.backend.Detector,
                    monitor_screen=self,
                    violation_backend=self.thread.backendUI.backend
                )
                progress.close()
                
            except RuntimeError as e:
                progress.close()
                QMessageBox.critical(
                    self,
                    "Initialization Failed",
                    f"Failed to initialize Violation Screen:\n\n{str(e)}\n\n"
                    "This is usually caused by:\n"
                    "• Unstable network connection (IP cameras)\n"
                    "• Camera disconnection during initialization\n\n"
                    "Please check your camera connection and try again."
                )
                self.append_log(f"❌ ViolationScreen RuntimeError: {e}")
                self.violation_window = None
                return
                
            except Exception as e:
                progress.close()
                QMessageBox.critical(
                    self,
                    "Initialization Failed",
                    f"Failed to create Violation Screen:\n\n{str(e)}\n\n"
                    "Please check logs for details."
                )
                self.append_log(f"❌ ViolationScreen creation failed: {e}")
                self.violation_window = None
                return
            
            progress.close()
            
            if self.violation_window is None:
                QMessageBox.critical(
                    self,
                    "Creation Failed",
                    "Failed to create Violation Screen (unknown error)."
                )
                return
            
            original_close = self.violation_window.closeEvent
            
            def on_violation_close(event):
                self.append_log("🔴 Violation Window Closing...")
                self.violation_window = None
                original_close(event)
            
            self.violation_window.closeEvent = on_violation_close
            
            self.violation_window.show()
            self.append_log(" Violation Monitor Opened", log_type="INFO")
            
        except Exception as e:
            self.append_log(f"❌ Error opening Violation Screen: {e}")
            
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred:\n\n{str(e)}\n\n"
                "Please restart the application."
            )
            
            self.violation_window = None
    
    def stop_saving(self):
        self.is_saving = False
        if self.thread:
            self.thread.backendUI.backend.set_save_options(False)
        self.append_log("🛑 Saving stopped")
        self.btn_save.setText(" Start Recording")
        self.btn_save.setStyleSheet(self.default_card_style)
    
    def auto_open_violation_for_full_monitor(self):
        """Auto-open violation screen for Full Monitor mode"""
        try:
            # Check if already open
            if hasattr(self, 'violation_window') and self.violation_window is not None:
                try:
                    if self.violation_window.isVisible():
                        self.append_log("⚠️ Violation screen already open", log_type="INFO")
                        return
                except RuntimeError:
                    self.violation_window = None

            # Validate before opening
            if not self._validate_camera_stability():
                self.append_log("⚠️ Camera not stable, skipping violation screen", log_type="WARNING")
                return

            if not self.check_required_detection_classes_for_voilation():
                self.append_log("⚠️ Required detection classes not selected", log_type="WARNING")
                return

            # Open violation screen
            self.append_log("🔄 Opening Violation Monitor...", log_type="INFO")

            self.violation_window = ViolationScreen(
                detector=self.thread.backendUI.backend.Detector,
                monitor_screen=self,
                violation_backend=self.thread.backendUI.backend
            )

            # Setup close handler
            original_close = self.violation_window.closeEvent

            def on_violation_close(event):
                self.violation_window = None
                original_close(event)

            self.violation_window.closeEvent = on_violation_close

            self.violation_window.show()
            self.append_log(" Violation Monitor opened (Full Monitor)", log_type="INFO")

        except Exception as e:
            self.append_log(f"❌ Failed to open Violation Monitor: {str(e)}", log_type="ERROR")
            self.append_log(f"❌ Error opening violation screen: {e}")

    def save_options(self):
        dialog = SaveDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            save_type, save_root = dialog.get_data()
            
            os.makedirs(save_root, exist_ok=True)
        
            self.is_saving = True
            self.btn_save.setText("⏹ Stop Recording")
            self.btn_save.setStyleSheet(self.active_style)
        
            self.thread.backendUI.backend.set_save_options(True, save_type, save_root)
        
            self.append_log(f"💾 Saving started ({save_type})")
            self.append_log(f"📂 Location: {os.path.abspath(save_root)}")

    def closeEvent(self, event):
        if self.thread:
            self.thread.stop()
            self.thread = None
        event.accept()

class ViolationScreen(BaseMonitorScreen):
    saved_violation_selection = []
    violation_log_signal = pyqtSignal(str, str, object)
    
    def __init__(self, detector, monitor_screen, violation_backend,log_callback=None):
        super().__init__(screen_type="violation")
        self.log_callback = log_callback
        
        # Block frame callbacks during initialization
        self._initialization_complete = False
        self._init_lock = threading.Lock()
        
        try:
            with self._init_lock:
                # Violation Screen initialization locked
                
                # Validate inputs
                if detector is None:
                    raise ValueError("Detector cannot be None")
                if monitor_screen is None:
                    raise ValueError("Monitor screen cannot be None")
                if violation_backend is None:
                    raise ValueError("Violation backend cannot be None")
                
                # Core attributes
                self.is_initializing = True
                self.detector = detector
                self.violation_backend = violation_backend
                self.monitor = monitor_screen
                self.violation_active = False
                
                # Log queue
                self._violation_log_queue = queue.Queue()
                self._log_timer = QTimer(self)
                self._log_timer.timeout.connect(self._process_violation_logs)
                self._log_timer.start(100)
                
                self._last_violation_log = {}
                self._violation_log_cooldown = 0.3
                
                # Initialize managers
                self.data_manager = ViolationDataManager()
                self.alert_manager = AlertManager()
                throttler = AlertThrottler(throttle_interval_minutes=15)
                self.alert_manager.set_throttler(throttler)
                self.append_log("Alert Manager Initialized With Throttling")
                
                # Create UI
                try:
                    self.setWindowTitle("Violation Monitor")
                    self.resize(1400, 800)
                    self.setMinimumSize(1280, 800)
                    self.center_on_screen()  #  From base class
                    
                    self.create_main_layout()  #  From base class
                    
                    if self.video_frame is None:
                        raise RuntimeError("video_frame was not created")
                    
                    try:
                        _ = self.video_frame.isVisible()
                    except RuntimeError:
                        raise RuntimeError("video_frame was created but is not accessible")
                    
                     # Phase 2: UI created and verified
                    
                except Exception as e:
                    print(f"❌ FATAL: UI creation failed: {e}")
                    raise
                
                # Load classes
                try:
                    if not hasattr(self.detector, 'model'):
                        raise AttributeError("Detector has no model attribute")
                    
                    self.load_violation_classes()
                    self.restore_selection()
                    # Phase 3: Classes loaded
                    
                except Exception as e:
                    print(f"⚠️ WARNING: Class loading failed: {e}")
                
                # Connect log signal
                try:
                    self.violation_log_signal.connect(
                        lambda msg: self.safe_append_log(msg),
                        Qt.QueuedConnection
                    )
                    print(" Phase 4: Log signal connected")
                    
                except Exception as e:
                    print(f"⚠️ WARNING: Log signal connection failed: {e}")
                
                # Set violation callback
                try:
                    if hasattr(self.violation_backend, 'set_violation_callback'):
                        self.violation_backend.set_violation_callback(self.on_violation_detected)
                        print(" Phase 5: Violation callback set")
                    else:
                        print("⚠️ WARNING: Backend has no set_violation_callback method")
                        
                except Exception as e:
                    print(f"⚠️ WARNING: Violation callback setup failed: {e}")
                
                # Connect frame signals
                try:
                    if not hasattr(self.monitor, 'thread'):
                        raise RuntimeError("Monitor has no thread attribute")
                    
                    if self.monitor.thread is None:
                        raise RuntimeError("Monitor thread is None")
                    
                    if not self.monitor.thread.isRunning():
                        raise RuntimeError("Monitor thread is not running")
                    
                    if not hasattr(self.monitor.thread, 'violation_pixmap_signal'):
                        raise RuntimeError("Thread has no violation_pixmap_signal")
                    
                    self.monitor.thread.violation_pixmap_signal.connect(
                        self.update_violation_video,
                        Qt.QueuedConnection
                    )
                    print(" Phase 6a: Frame signal connected")
                    
                    self.monitor.thread.set_violation_ui_label(self.video_frame)
                    print(" Phase 6b: UI label registered with thread")
                    
                except Exception as e:
                    print(f"❌ WARNING: Frame connection failed: {e}")
                    
                    QTimer.singleShot(1000, self.show_frame_connection_warning)
                
                # Complete initialization
                self.is_initializing = False
                self._initialization_complete = True
                
                print(" Phase 7: ViolationScreen initialization complete")
                print("🔓 Initialization lock released")
        
        except Exception as e:
            print(f"❌ FATAL: ViolationScreen initialization failed: {e}")
            
            self._initialization_complete = False
            self.is_initializing = False
            
            raise
    
    def show_frame_connection_warning(self):
        """Show warning if frame connection failed"""
        try:
            if not self.isVisible():
                return
            
            QMessageBox.warning(
                self,
                "Video Feed Warning",
                "Video feed connection failed.\n\n"
                "Possible causes:\n"
                "• Network instability (IP camera)\n"
                "• Camera disconnected\n"
                "• Detection not running\n\n"
                "Try:\n"
                "1. Restart detection in Monitor Screen\n"
                "2. Check camera connection\n"
                "3. Reopen Violation Monitor"
            )
        except Exception:
            pass
    
    def add_left_sidebar_buttons(self, layout):
        """Add update button for violation classes"""
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(15, 10, 15, 20)
        
        self.btn_update_violation = QPushButton("Update Violation Classes")
        self.btn_update_violation.setFixedHeight(42)
        self.btn_update_violation.setCursor(Qt.PointingHandCursor)
        self.btn_update_violation.setStyleSheet(
        f"background-color: {PRIMARY_COLOR}; color: white; "
        "border-radius: 6px; font-weight: bold; padding: 10px; "
        "border: none;")
        self.btn_update_violation.clicked.connect(self.on_update_violation_clicked)
        
        button_layout.addWidget(self.btn_update_violation)
        layout.addWidget(button_container)
    
    def create_control_buttons(self):
        """Create violation-specific control buttons"""
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)

        self.startViolationBtn = QPushButton("▶ Start Violation Detection")
        self.startViolationBtn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.startViolationBtn.setCursor(Qt.PointingHandCursor)
        self.startViolationBtn.setEnabled(False)
        self.startViolationBtn.setStyleSheet(self.default_style)
        self.startViolationBtn.setFixedHeight(45)
        self.startViolationBtn.clicked.connect(self.toggle_violation_detection)

        self.btn_configure_alerts = QPushButton("⚙️ Configure Alerts")
        self.btn_configure_alerts.setCursor(Qt.PointingHandCursor)
        self.btn_configure_alerts.setStyleSheet(self.default_card_style)
        self.btn_configure_alerts.setFixedHeight(45)
        self.btn_configure_alerts.clicked.connect(self.configure_alerts)

        self.btn_throttle_settings = QPushButton("⏱️ Throttle Settings")
        self.btn_throttle_settings.setCursor(Qt.PointingHandCursor)
        self.btn_throttle_settings.setStyleSheet(self.default_card_style)
        self.btn_throttle_settings.setFixedHeight(45)
        self.btn_throttle_settings.clicked.connect(self.open_throttle_settings)

        self.btn_toggle_alerts = QPushButton("📧 Enable Alerts")
        self.btn_toggle_alerts.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_alerts.setStyleSheet(self.default_card_style)
        self.btn_toggle_alerts.setFixedHeight(45)
        self.btn_toggle_alerts.clicked.connect(self.toggle_alerts)

        self.btn_export = QPushButton("📊 Export Report")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setStyleSheet(self.default_card_style)
        self.btn_export.setFixedHeight(45)
        self.btn_export.clicked.connect(self.export_violation_report)

        controls_layout.addWidget(self.startViolationBtn)
        controls_layout.addWidget(self.btn_configure_alerts)
        controls_layout.addWidget(self.btn_throttle_settings)
        controls_layout.addWidget(self.btn_toggle_alerts)
        controls_layout.addWidget(self.btn_export)
        controls_layout.addStretch()

        return controls_layout

    def handle_disconnect(self):
        """Stop violation detection and close"""
        if self.violation_active:
            self.stop_violation_detection()
        self.close()
    
    def update_violation_video(self, qt_img):
        """ViolationScreen frame update - delegates to base class"""
        if not self._initialization_complete:
            return
        
        if getattr(self, 'is_initializing', True):
            return
        
        self.update_video_frame(qt_img)  #  From base class
    
    def get_selected_violation_class_ids(self, return_type="name"):
        """ UPDATED: Use panel's built-in methods"""
        if return_type.lower() == "name":
            return self.class_selection_panel.get_selected_classes()

        #  Temporarily set backend if not set
        if not self.class_selection_panel.backend_detector:
            self.class_selection_panel.backend_detector = self.detector

        return self.class_selection_panel.get_selected_class_ids()

    def load_violation_classes(self):
        """ UPDATED: Link detector to panel for auto-sync"""
        if not self.detector or not hasattr(self.detector, "model"):
            self.append_log("❌ Detector Or Model Not Ready")
            return

        
        class_names = list(self.detector.model.names.values())
        self.append_log(f"Loading Violation Classes: {class_names}")


        self.class_selection_panel.populate_classes(
            class_names=class_names,
            default_checked=[]
        )

        # Keep checkboxes reference for backward compatibility
        self.checkboxes = self.class_selection_panel.checkboxes
        self.append_log(f" Created {len(self.checkboxes)} Violation Checkboxes")
    
    def restore_selection(self):
        """Restore previously selected classes"""
        for class_name, checkbox in self.checkboxes.items():
            if class_name in ViolationScreen.saved_violation_selection:
                checkbox.setChecked(True)
    
    def on_update_violation_clicked(self):

        """Handle 'Update Violation Classes' button click with negative class warning"""
        print("Update Violation Classes clicked")
        
        if not self.monitor.is_detection_running:
            msg1 = QMessageBox(self)
            msg1.setIcon(QMessageBox.Information)
            msg1.setCursor(Qt.PointingHandCursor)
            msg1.setWindowTitle("Detection Not Runing")
            msg1.setText(
                f"⚠️ IMPORTANT:\n\n"
                f"Please Start Detection Or Tracking To Use Voilation Monitor"
            )
            msg1.setStyleSheet(f"""
                    QMessageBox Icon {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                                      
                    QMessageBox {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                    QMessageBox QLabel {{
                        color: {TEXT_COLOR};
                        font-size: 15px;
                        background-color: {CARD_COLOR};
                    }}
                    QMessageBox QPushButton {{
                        background-color: {PRIMARY_COLOR};
                        color: white;
                        border: none;
                        padding: 8px 20px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 80px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #0284c7;
                    }}
                """)
            btn_cancel = msg1.addButton("OK", QMessageBox.RejectRole)
            msg1.exec_()
            if msg1.clickedButton() == btn_cancel:
                return
        
        selected_classes = self.get_selected_violation_class_ids(return_type="name")
        negative_classes = [cls for cls in selected_classes if self.is_negative_class(cls)]
        
        if negative_classes:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setCursor(Qt.PointingHandCursor)
            msg.setWindowTitle("⚠️ Negative Classes Detected")
            msg.setText(
                f"You have selected negative classes:\n\n"
                f"{', '.join(negative_classes)}\n\n"
                f"⚠️ IMPORTANT:\n"
                f"• Negative classes (e.g., 'no hard hat') will trigger violations when DETECTED\n"
                f"• Positive classes (e.g., 'hard hat') will trigger violations when NOT DETECTED\n\n"
                f"Please verify your selection is correct to avoid false alarms."
            )
            msg.setStyleSheet(f"""
                    QMessageBox Icon {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                                      
                    QMessageBox {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                    QMessageBox QLabel {{
                        color: {TEXT_COLOR};
                        font-size: 15px;
                        background-color: {CARD_COLOR};
                    }}
                    QMessageBox QPushButton {{
                        background-color: {PRIMARY_COLOR};
                        color: white;
                        border: none;
                        padding: 8px 20px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 80px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #0284c7;
                    }}
                """)
            
            btn_continue = msg.addButton("Continue Anyway", QMessageBox.AcceptRole)
            btn_cancel = msg.addButton("Go Back", QMessageBox.RejectRole)
            
            msg.exec_()
            
            if msg.clickedButton() == btn_cancel:
                return
        
        missing_ids = self.get_missing_violation_class_ids()
        
        if missing_ids:
            synced = self.show_violation_sync_popup(missing_ids)
            if not synced:
                return
        
        self.send_violation_classes_to_backend()
        self.startViolationBtn.setEnabled(True)
    
    def is_negative_class(self, class_name):
        """Check if class name is negative"""
        negative_prefixes = ["no ", "no-", "without ", "without-", "not ", "not-"]
        class_lower = class_name.lower()
        return any(class_lower.startswith(prefix) for prefix in negative_prefixes)
    
    def send_violation_classes_to_backend(self):
        """Send selected violation classes to backend ViolationDetector"""
        violation_names = self.get_selected_violation_class_ids(return_type="name")
        
        if not violation_names:
            self.append_log("⚠️ No Violation Classes Selected")
            return
        
        self.violation_backend.set_violation_classes(violation_names)
        
        self.append_log(f"📤 Required PPE: {', '.join(violation_names)}")
        self.append_log(f" Violation Classes Sent To Backend: {violation_names}")
    
    def get_missing_violation_class_ids(self):
        """Check which violation classes are not selected in Monitor"""
        detection_ids = self.monitor.get_selected_classes_ids(return_type="id")
        violation_ids = self.get_selected_violation_class_ids(return_type="id")
        
        missing = [vid for vid in violation_ids if vid not in detection_ids]
        return missing
    
    def show_violation_sync_popup(self, missing_ids):
        """Show popup to auto-check missing classes in Monitor"""
        if getattr(self, "skip_violation_sync_prompt", False):
            self.auto_check_monitor_classes(missing_ids)
            return True
        
        missing_names = [self.detector.model.names[i] for i in missing_ids]
        
        msg = QMessageBox(self)
        msg.setStyleSheet(f"""
                    QMessageBox Icon {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                                      
                    QMessageBox {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                    QMessageBox QLabel {{
                        color: {TEXT_COLOR};
                        font-size: 15px;
                        background-color: {CARD_COLOR};
                    }}
                    QMessageBox QPushButton {{
                        background-color: {PRIMARY_COLOR};
                        color: white;
                        border: none;
                        padding: 8px 20px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 80px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #0284c7;
                    }}
                    QCheckBox{{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    
                    }}
                """)
        msg.setIcon(QMessageBox.Warning)
        msg.setCursor(Qt.PointingHandCursor)
        msg.setWindowTitle("Missing Detection Classes")
        msg.setText(
            "The Following Classes Are Selected For Violation But Not In Monitor:\n\n"
            f"{', '.join(missing_names)}\n\n"
            "Auto-Check Them In Monitor Screen?"
        )
        
        dont_ask = QCheckBox("Don't Ask Again")
        msg.setCheckBox(dont_ask)
        
        btn_auto = msg.addButton("Auto-Check", QMessageBox.AcceptRole)
        btn_close = msg.addButton("Close", QMessageBox.RejectRole)
        
        
        if dont_ask.isChecked():
            self.skip_violation_sync_prompt = True
        
        if msg.clickedButton() == btn_auto:
            self.auto_check_monitor_classes(missing_ids)
            return True
        
        return False
    
    def auto_check_monitor_classes(self, class_ids):
        """Automatically check classes in Monitor Screen"""
        model = self.detector.model
        checked = []
        
        for cls_id in class_ids:
            cls_name = model.names.get(cls_id)
            if cls_name in self.monitor.checkboxes:
                cb = self.monitor.checkboxes[cls_name]
                cb.setChecked(True)
                checked.append(cls_name)
        
        self.append_log(f" Auto-Checked In Monitor: {', '.join(checked)}")
    
    def start_violation_detection(self):
        """Start violation checking in backend"""
        
        if not self.monitor.is_detection_running:
            msg1 = QMessageBox(self)
            msg1.setIcon(QMessageBox.Information)
            msg1.setCursor(Qt.PointingHandCursor)
            msg1.setWindowTitle("Detection Not Runing")
            msg1.setText(
                f"⚠️ IMPORTANT:\n\n"
                f"Detection Or Tracking Must Be Runing In Monitor Screen\n\n"
                f"Please Start Detection Or Tracking To Start Voilation Monitoing"
            )
            msg1.setStyleSheet(f"""
                    QMessageBox Icon {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                                      
                    QMessageBox {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                    QMessageBox QLabel {{
                        color: {TEXT_COLOR};
                        font-size: 15px;
                        background-color: {CARD_COLOR};
                    }}
                    QMessageBox QPushButton {{
                        background-color: {PRIMARY_COLOR};
                        color: white;
                        border: none;
                        padding: 8px 20px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 80px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #0284c7;
                    }}
                """)
            btn_cancel = msg1.addButton("OK", QMessageBox.RejectRole)
            msg1.exec_()
            if msg1.clickedButton() == btn_cancel:
                return
        
        violation_names = self.get_selected_violation_class_ids(return_type="name")
        if not violation_names:
            msg1 = QMessageBox(self)
            msg1.setIcon(QMessageBox.Information)
            msg1.setCursor(Qt.PointingHandCursor)
            msg1.setWindowTitle("No Classes Selected")
            msg1.setText(
                f"⚠️ IMPORTANT:\n\n"
                f"Please Select At Least One Violation Class.\n\n"
            )
            msg1.setStyleSheet(f"""
                    QMessageBox Icon {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                                      
                    QMessageBox {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                    QMessageBox QLabel {{
                        color: {TEXT_COLOR};
                        font-size: 15px;
                        background-color: {CARD_COLOR};
                    }}
                    QMessageBox QPushButton {{
                        background-color: {PRIMARY_COLOR};
                        color: white;
                        border: none;
                        padding: 8px 20px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 80px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #0284c7;
                    }}
                """)
            btn_cancel = msg1.addButton("OK", QMessageBox.RejectRole)
            msg1.exec_()
            if msg1.clickedButton() == btn_cancel:
                return
        
        self.violation_backend.enable_violation_detection(True)
        self.violation_active = True
        
        # button styling
        self.startViolationBtn.setText("⏸ Pause Violation Detection")
        self.startViolationBtn.setStyleSheet(self.active_style)  
        
        self.status_badge.setText("🔴 Active")
        self.status_badge.setStyleSheet(
        "color: #EF4444; font-weight: bold; "
        "background-color: rgba(239, 68, 68, 0.1); "
        "padding: 5px 10px; border-radius: 12px;")
        
        self.append_log("🔴 Violation Detection Started In Backend")
    
    def stop_violation_detection(self):
        """Stop violation checking in backend"""
        self.append_log("Stopping Violation Detection")
        
        self.violation_backend.enable_violation_detection(False)
        self.violation_active = False
        
        self.startViolationBtn.setText("▶ Start Violation Detection")
        self.startViolationBtn.setStyleSheet(self.default_style)  # Use class variable
        
        self.status_badge.setText("⏸ Idle")
        self.status_badge.setStyleSheet(
        "color: #F59E0B; font-weight: bold; "
        "background-color: rgba(245, 158, 11, 0.1); "
        "padding: 5px 10px; border-radius: 12px;")
        
        self.append_log("⏸ Violation Detection Stopped In Backend")
    def toggle_violation_detection(self):
        """Toggle violation detection on/off"""
        if self.violation_active:
            self.stop_violation_detection()
        else:
            self.start_violation_detection()
    
    def on_violation_detected(self, violations):
        """Process batched violations from backend"""
        if not violations:
            return

        # Limit to 10 persons max per email
        violations_to_process = violations[:10]

        try:
            # Capture all violations as a batch
            batch_id, cropped_paths = self.violation_backend.capture_batch_violation_data(
                violations_list=violations_to_process,
                data_manager=self.data_manager
            )
            
            if not batch_id:
                print("⚠️ Failed To Capture Batch Violation")
                return
            
            # Get batch metadata
            batch_record = None
            for record in self.data_manager.violation_log:
                if record.get("batch_id") == batch_id:
                    batch_record = record
                    break
            
            if not batch_record:
                print("⚠️ Batch Record Not Found")
                return
            
            # Send one email for all persons
            if self.alert_manager.enabled:
                full_path = self.data_manager.base_dir / batch_record["images"]["full_frame"]
                
                try:
                    sent, reason = self.alert_manager.queue_batch_alert(
                        batch_violation_data=batch_record,
                        cropped_image_paths=[str(p) for p in cropped_paths],
                        full_image_path=str(full_path)
                    )
                    
                    if sent:
                        log_msg = f"{len(violations_to_process)} persons - {batch_record['severity']} (Batch: {batch_id[:8]}) 📧 {reason}"
                    else:
                        log_msg = f"{len(violations_to_process)} persons - {batch_record['severity']} (Batch: {batch_id[:8]}) ⏸️ {reason}"
                except Exception as e:
                    log_msg = f"{len(violations_to_process)} persons - {batch_record['severity']} (Batch: {batch_id[:8]})"
                    self.append_log(f"⚠️ Alert queue error: {e}")
            else:
                log_msg = f"{len(violations_to_process)} persons - {batch_record['severity']} (Batch: {batch_id[:8]})"
            
            # Log once for the batch
            try:
                self._violation_log_queue.put((log_msg, "VIOLATION", {
                    "batch_id": batch_id,
                    "total_persons": len(violations_to_process),
                    "severity": batch_record['severity']
                }))
            except Exception as e:
                print(f"⚠️ Queue error: {e}")
        
        except Exception as e:
            print(f"❌ Batch violation processing error: {e}")
    
    def _process_violation_logs(self):
        """Process violation logs in batches (prevents UI flooding)"""
        processed = 0
        max_per_batch = 5
        
        while processed < max_per_batch:
            try:
                log_msg, log_type, metadata = self._violation_log_queue.get_nowait()
                
                try:
                    self.log_panel.append_log(log_msg, log_type, metadata)
                except Exception as e:
                    print(f"⚠️ Error appending log: {e}")
                
                processed += 1
                
            except queue.Empty:
                break
            except Exception as e:
                print(f"⚠️ Error processing log: {e}")
                break
    
    def safe_append_log(self, message):
        """Queue logs instead of direct append (prevents crash)"""
        try:
            if not self.isVisible():
                return
            
            log_type = "VIOLATION"
            metadata = None
            
            self._violation_log_queue.put((message, log_type, metadata))
            
        except RuntimeError:
            pass
        except Exception as e:
            print(f"⚠️ Log queue error: {e}")
    
    def configure_alerts(self):
        """ UPDATED: Use built-in dialog method"""
        if self.alert_manager.show_config_dialog(self):
           print(" Alert configuration saved")
    
    def open_throttle_settings(self):
        """ UPDATED: Use built-in dialog method"""
        if self.alert_manager.throttler.show_settings_dialog(self):
            print(" Throttle settings updated")
    
    def toggle_alerts(self):
        """Enable/disable alert system with immediate feedback"""
        if not self.alert_manager.enabled:
            if not self.alert_manager.sender_email or not self.alert_manager.recipient_emails:
                QMessageBox.warning(
                    self,
                    "Not Configured",
                    "Please configure email settings first."
                )
                return
            
            self.btn_toggle_alerts.setText("📕 Disable Alerts")
            self.btn_toggle_alerts.setStyleSheet(self.active_style)  # Red when active
            self.btn_toggle_alerts.repaint()
            QApplication.processEvents()
            
            self.alert_manager.enable(True)
            self.append_log("📧 Email alerts ENABLED", log_type="INFO")
        else:
            self.btn_toggle_alerts.setText("📧 Enable Alerts")
            self.btn_toggle_alerts.setStyleSheet(self.default_card_style)
            self.btn_toggle_alerts.repaint()
            QApplication.processEvents()
            
            self.alert_manager.enable(False)
            self.append_log("📕 Email alerts DISABLED", log_type="INFO")
    
    def export_violation_report(self):
        """Export violation summary report"""
        try:
            summary_path = self.data_manager.export_summary()
            
            if summary_path:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Information)
                msg.setCursor(Qt.PointingHandCursor)
                msg.setWindowTitle("Report Exporter")
                msg.setText(
                    f"Report Exported\n\n"
                    f"Violation report exported to:\n{summary_path}\n\n"
                    f"Total violations captured: {len(self.data_manager.violation_log)}"
                )
                msg.setStyleSheet(f"""
                    QMessageBox Icon {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                                      
                    QMessageBox {{
                        background-color: {CARD_COLOR};
                        color: {TEXT_COLOR};
                    }}
                    QMessageBox QLabel {{
                        color: {TEXT_COLOR};
                        font-size: 15px;
                        background-color: {CARD_COLOR};
                    }}
                    QMessageBox QPushButton {{
                        background-color: {PRIMARY_COLOR};
                        color: white;
                        border: none;
                        padding: 8px 20px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 80px;
                    }}
                    QMessageBox QPushButton:hover {{
                        background-color: #0284c7;
                    }}
                """)
                
                btn_cancel = msg.addButton("Go Back", QMessageBox.RejectRole)
                msg.exec_()
            
                if msg.clickedButton() == btn_cancel:
                    return

            else:
                QMessageBox.warning(self, "Export Failed", "Failed to export report.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export error: {str(e)}")
    
    def closeEvent(self, event):
        """Enhanced closeEvent with cleanup"""
        try:
            self.append_log("🔴 ViolationScreen closing...")
            
            if hasattr(self, '_log_timer'):
                self._log_timer.stop()
                self.append_log(" Log timer stopped")
            
            if self.monitor and hasattr(self.monitor, 'thread') and self.monitor.thread:
                try:
                    self.monitor.thread.clear_violation_ui_label()
                    self.append_log(" Cleared violation label from VideoThread")
                except Exception as e:
                    self.append_log(f"⚠️ Error clearing label: {e}")
            
            try:
                if self.monitor and hasattr(self.monitor, 'thread') and self.monitor.thread:
                    self.monitor.thread.violation_pixmap_signal.disconnect()
                    self.append_log(" Violation frame signal disconnected")
            except TypeError:
                pass
            except Exception as e:
                self.append_log(f"⚠️ Error disconnecting signal: {e}")
            
            if hasattr(self, 'alert_manager'):
                try:
                    self.alert_manager.stop_alert_worker()
                    self.append_log(" Alert worker stopped")
                except Exception as e:
                    self.append_log(f"⚠️ Error stopping alert worker: {e}")
            
            selected = self.get_selected_violation_class_ids(return_type="name")
            ViolationScreen.saved_violation_selection = selected
            self.append_log(f"💾 Saved violation selection: {selected}")
            
            if self.violation_active:
                try:
                    self.stop_violation_detection()
                except Exception as e:
                    self.append_log(f"⚠️ Error stopping violation detection: {e}")
            
            try:
                if hasattr(self, 'violation_log_signal'):
                    self.violation_log_signal.disconnect()
            except Exception:
                pass
            
            try:
                if hasattr(self, 'video_frame'):
                    self.video_frame.clear()
                    self.video_frame = None
                    self.append_log(" video_frame widget cleared")
            except Exception as e:
                self.append_log(f"⚠️ Error clearing video_frame: {e}")
            
            event.accept()
            self.append_log(" ViolationScreen closed cleanly")
            
        except Exception as e:
            self.append_log(f"❌ Error in closeEvent: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PPE Safety Monitor")
        self.resize(1400, 800)
        self.setMinimumSize(1280, 800)
        #  Center window
        self.center_on_screen()
        self.setStyleSheet(STYLESHEET)

        self.auth_manager = AuthManager()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_screen = LoginScreen(self.auth_manager, self.go_to_connection, self.go_to_signup)
        self.signup_screen = SignupScreen(self.auth_manager, self.go_to_login_from_signup, self.go_to_login)
        self.connection_screen = ConnectionScreen(self.go_to_monitor)
        self.monitor_screen = MonitorScreen(self.go_to_connection)
        
        self.stack.addWidget(self.login_screen)
        self.stack.addWidget(self.signup_screen)
        self.stack.addWidget(self.connection_screen)
        self.stack.addWidget(self.monitor_screen)

        self.stack.setCurrentWidget(self.connection_screen)

    def center_on_screen(self):
        """Center the window on screen"""
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        center_point = screen.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def go_to_signup(self):
        self.stack.setCurrentWidget(self.signup_screen)

    def go_to_login(self):
        self.stack.setCurrentWidget(self.login_screen)

    def go_to_login_from_signup(self):
        self.login_screen.error_label.setText("Signup successful! Please login.")
        self.login_screen.error_label.setStyleSheet(f"color: {PRIMARY_COLOR};")
        self.stack.setCurrentWidget(self.login_screen)

    def go_to_monitor(self, source, model_path,tracking_path,use_gpu):
        self.monitor_screen.start_stream(source, model_path, tracking_path, use_gpu)
        self.stack.setCurrentWidget(self.monitor_screen)

    def go_to_connection(self):
        self.stack.setCurrentWidget(self.connection_screen)

if __name__ == "__main__":
    # Set AppUserModelID for Windows Taskbar Icon
    # This is CRITICAL for the taskbar icon to show up instead of the Python logo
    import ctypes
    myappid = 'custom.ppedetection.monitor.v1.0.0' 
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print(f"⚠️ Could not set AppID: {e}")

    app = QApplication(sys.argv)
    
    # Set app-wide icon with absolute path to the PNG
    # PNGs often render better in the taskbar for PyQt apps
    icon_path = os.path.abspath("PPE.png")
    app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())