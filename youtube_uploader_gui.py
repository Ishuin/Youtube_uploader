import sys
import os
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, 
                             QWidget, QFileDialog, QProgressBar, QListWidget, QLabel, QFrame,
                             QComboBox, QCheckBox, QGroupBox, QRadioButton, QListWidgetItem)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from youtube_uploader import get_authenticated_service, DataStorage, create_or_get_playlist, upload_video, process_directory, QuotaExceededError
import tkinter as tk
from tkinter import messagebox

class UploaderThread(QThread):
    update_overall_progress = pyqtSignal(int, int, int)  # progress, total files, processed files
    update_file_progress = pyqtSignal(str, str, int, float)  # playlist, video, progress, remaining time
    update_status = pyqtSignal(str)
    file_completed = pyqtSignal(str, str, str)  # playlist, video, video_id

    def __init__(self, directory, storage, dry_run=False):
        super().__init__()
        self.directory = directory
        self.storage = storage
        self.dry_run = dry_run
        self.is_paused = False
        self.is_cancelled = False

    def _process_files(self, youtube=None):
        total_files = sum([len(files) for r, d, files in os.walk(self.directory) if any(f.endswith(('.mp4', '.avi', '.mov', '.mkv', '.m4v')) for f in files)])
        processed_files = 0

        for dirpath, dirnames, filenames in os.walk(self.directory):
            rel_path = os.path.relpath(dirpath, self.directory)
            if rel_path == '.':
                continue

            playlist_name = '_'.join(rel_path.split(os.path.sep))
            video_files = [f for f in filenames if f.endswith(('.mp4', '.avi', '.mov', '.mkv', '.m4v'))]

            if video_files:
                if self.dry_run:
                    playlist_id = f"DRY_RUN_PLAYLIST_{playlist_name}"
                    self.update_status.emit(f"Dry run: Processing {playlist_name}")
                else:
                    playlist_id = create_or_get_playlist(youtube, playlist_name, self.storage)
                    self.update_status.emit(f"Uploading to {playlist_name}")

                for video in video_files:
                    while self.is_paused:
                        time.sleep(0.1)
                    if self.is_cancelled:
                        return
                    video_path = os.path.join(dirpath, video)
                    video_path = os.path.normpath(video_path)
                    video_title = os.path.splitext(video)[0]
                    
                    if self.dry_run:
                        self.storage.add_dry_run_video(video_title, playlist_id, video_path)
                        for progress in range(0, 101, 10):
                            if self.is_cancelled:
                                return
                            time.sleep(0.1)  # Simulate processing time
                            remaining_time = (100 - progress) * 0.1
                            self.update_file_progress.emit(playlist_name, video_title, progress, remaining_time)
                    else:
                        try:
                            video_id, video_title, _ = upload_video(youtube, video_path, playlist_id, self.storage, self.update_file_progress)
                            if video_id:
                                self.update_status.emit(f"Uploaded: {video_title}")
                                self.file_completed.emit(playlist_name, video_title, video_id)
                            else:
                                self.update_status.emit(f"Failed to upload: {os.path.basename(video_path)}")
                        except QuotaExceededError as e:
                            messagebox.showerror("Quota Exceeded", str(e))
                            self.update_status.emit("Upload process stopped due to exceeded quota.")
                            break  # Stop the upload process when quota exceeded
                        except Exception as e:
                            error_message = f"Error uploading {os.path.basename(video_path)}: {str(e)}"
                            self.update_status.emit(error_message)
                            messagebox.showerror("Upload Error", error_message)
                            if not messagebox.askyesno("Continue Uploading", "An error occurred. Do you want to continue with the next video?"):
                                break

                    processed_files += 1
                    self.update_overall_progress.emit(int((processed_files / total_files) * 100), total_files, processed_files)

        if self.dry_run:
            self.update_status.emit("Dry run completed!")
        else:
            self.update_status.emit("Upload completed!")

    def dry_run_process(self):
        self._process_files()

    def upload_process(self):
        youtube = get_authenticated_service()
        self._process_files(youtube)

    def run(self):
        if self.dry_run:
            self.dry_run_process()
        else:
            self.upload_process()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Bulk Uploader")
        self.setGeometry(100, 100, 800, 600)
        self.setup_ui()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()

        # Directory selection
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("No directory selected")
        dir_button = QPushButton("Select Directory")
        dir_button.clicked.connect(self.select_directory)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(dir_button)
        layout.addLayout(dir_layout)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        
        # Storage type
        storage_layout = QHBoxLayout()
        storage_label = QLabel("Storage Type:")
        self.storage_combo = QComboBox()
        self.storage_combo.addItems(["SQLite", "CSV"])
        storage_layout.addWidget(storage_label)
        storage_layout.addWidget(self.storage_combo)
        options_layout.addLayout(storage_layout)

        # Dry run option
        self.dry_run_checkbox = QCheckBox("Dry Run (No actual upload)")
        options_layout.addWidget(self.dry_run_checkbox)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Add Columns: Playlists and Videos
        self.playlist_list = QListWidget()  # Playlist column
        self.video_list = QListWidget()     # Video column
        column_layout = QHBoxLayout()
        column_layout.addWidget(self.playlist_list)
        column_layout.addWidget(self.video_list)
        layout.addLayout(column_layout)

        # Overall Progress
        self.overall_progress_label = QLabel("Overall Progress:")
        layout.addWidget(self.overall_progress_label)
        self.overall_progress_bar = QProgressBar()
        layout.addWidget(self.overall_progress_bar)

        # Current file progress
        self.current_file_label = QLabel("Current File:")
        layout.addWidget(self.current_file_label)
        self.current_file_progress_bar = QProgressBar()
        layout.addWidget(self.current_file_progress_bar)

        # Status label
        self.status_label = QLabel("Ready to upload")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Control buttons
        button_layout = QHBoxLayout()
        self.upload_button = QPushButton("Start Upload")
        self.upload_button.clicked.connect(self.start_upload)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_upload)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.upload_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        main_widget.setLayout(layout)

        self.directory = None
        self.uploader_thread = None

    def select_directory(self):
        self.directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if self.directory:
            self.dir_label.setText(self.directory)
            self.upload_button.setEnabled(True)

    def _setup_uploader_thread(self, dry_run):
        storage_type = 'sqlite' if self.storage_combo.currentText() == "SQLite" else 'csv'
        storage_filename = 'youtube_uploader_data.sqlite' if storage_type == 'sqlite' else 'youtube_uploader_data.csv'
        self.storage = DataStorage(storage_type, storage_filename)
        self.uploader_thread = UploaderThread(self.directory, self.storage, dry_run)
        self.uploader_thread.update_overall_progress.connect(self.update_overall_progress)
        self.uploader_thread.update_file_progress.connect(self.update_file_progress)
        self.uploader_thread.update_status.connect(self.update_status)
        self.uploader_thread.file_completed.connect(self.file_completed)
        self.uploader_thread.finished.connect(self.upload_finished)
        self.uploader_thread.start()

    def start_upload(self):
        if not self.directory:
            return

        dry_run = self.dry_run_checkbox.isChecked()
        self._setup_uploader_thread(dry_run)

        self.upload_button.setEnabled(False)
        self.pause_button.setEnabled(not dry_run)
        self.cancel_button.setEnabled(True)

    def toggle_pause(self):
        if self.uploader_thread and not self.uploader_thread.dry_run:
            self.uploader_thread.is_paused = not self.uploader_thread.is_paused
            self.pause_button.setText("Resume" if self.uploader_thread.is_paused else "Pause")

    def cancel_upload(self):
        if self.uploader_thread:
            self.uploader_thread.is_cancelled = True
            self.upload_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.cancel_button.setEnabled(False)

    def update_overall_progress(self, progress, total_files, processed_files):
        self.overall_progress_bar.setValue(progress)
        self.overall_progress_label.setText(f"Overall Progress: {processed_files}/{total_files} files")

    def update_file_progress(self, playlist, video, progress, remaining_time):
        self.current_file_label.setText(f"Uploading {video} from {playlist}: {progress }%")
        self.current_file_progress_bar.setValue(progress)
        self.status_label.setText(f"Time left: {remaining_time:.2f}s")

    def update_status(self, status):
        self.status_label.setText(status)

    def file_completed(self, playlist, video, video_id):
        # Adding playlist and video titles to separate columns
        self.playlist_list.addItem(QListWidgetItem(playlist))
        self.video_list.addItem(QListWidgetItem(f"{video} (ID: {video_id})"))

    def upload_finished(self):
        self.upload_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.overall_progress_bar.setValue(100)
        self.current_file_progress_bar.setValue(100)
        self.current_file_label.setText("Upload completed")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())