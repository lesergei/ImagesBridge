New Features & Improvements
UI Enhancement: Replaced the custom editor list in preferences with a more "Blender-like" UI using UIList.

Better Error Handling:
The addon now checks for the existence of context.material before accessing its attributes, preventing crashes when no object is selected.

Improved image selection logic to avoid unexpected errors when no active image is found.

Improved Image Saving Workflow:
If an unsaved image is opened from the 3D View, the Texture Paint workspace will now be activated automatically before prompting the user to save the image.

Refactored Code Structure:
Simplified the get_active_image function for better reliability across different editors.
Enhanced operator execution flow to ensure a smoother experience.

Bug Fixes
Fixed Crash on Empty Scene: Prevented an error when all objects are deleted from the scene.
Fixed Context Errors: The addon now correctly handles cases where context.material is unavailable.
Fixed Save Prompt Behavior: Improved logic to ensure the save prompt appears only when needed.

General Improvements
Code Optimization: Reduced redundant operations for better performance.

Cleanup: Ensured __pycache__ is excluded from the final release.

Enjoy a smoother experience with ImagesBridge! 
