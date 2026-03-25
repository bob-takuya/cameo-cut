"""
Setup script for building CameoCut as a macOS application

Usage:
    python setup.py py2app

This will create a standalone .app bundle in the dist/ directory.
"""

from setuptools import setup

APP = ['src/main.py']
DATA_FILES = [
    ('resources', ['resources/presets.json']),
    ('resources/icons', [
        'resources/icons/cameocut.icns',
        'resources/icons/cameocut.png',
    ]),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'resources/icons/cameocut.icns',
    'plist': {
        'CFBundleName': 'CameoCut',
        'CFBundleDisplayName': 'CameoCut',
        'CFBundleIdentifier': 'com.cameocut.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'DXF File',
                'CFBundleTypeExtensions': ['dxf', 'DXF'],
                'CFBundleTypeRole': 'Editor',
                'LSHandlerRank': 'Alternate',
            }
        ],
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15',
    },
    'packages': ['PyQt6', 'ezdxf'],
    'includes': [
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
    ],
    'excludes': ['tkinter', 'matplotlib', 'scipy', 'pandas'],
    'semi_standalone': False,
    'site_packages': True,
}

setup(
    name='CameoCut',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
