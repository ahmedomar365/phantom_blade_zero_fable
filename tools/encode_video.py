"""Encodes build/frames/f_*.jpg into an H.264 MP4 with Blender's built-in encoder (no ffmpeg install needed).
Run: blender -b -P tools/encode_video.py -- <output.mp4> [fps]"""
import bpy, os, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = os.path.abspath(args[0]) if args else os.path.join(ROOT, 'video', 'showcase.mp4')
fps = int(args[1]) if len(args) > 1 else 30
frames = sorted(glob.glob(os.path.join(ROOT, 'build', 'frames', 'f_*.jpg')))
assert frames, 'no frames in build/frames'
os.makedirs(os.path.dirname(out), exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
img = bpy.data.images.load(frames[0])
sc.render.resolution_x, sc.render.resolution_y = img.size
sc.render.resolution_percentage = 100
sc.render.fps = fps
sc.frame_start, sc.frame_end = 1, len(frames)
sc.view_settings.view_transform = 'Standard'          # frames are already display-referred: do not grade them again
sc.view_settings.look = 'None'
sc.sequence_editor_create()
se = sc.sequence_editor
strips = se.strips if hasattr(se, 'strips') else se.sequences
st = strips.new_image('frames', frames[0], 1, 1)
for f in frames[1:]:
    st.elements.append(os.path.basename(f))
if hasattr(sc.render.image_settings, 'media_type'):      # Blender 5: video formats live behind a media type
    sc.render.image_settings.media_type = 'VIDEO'
sc.render.image_settings.file_format = 'FFMPEG'
ff = sc.render.ffmpeg
ff.format = 'MPEG4'
ff.codec = 'H264'
ff.constant_rate_factor = 'HIGH'
ff.ffmpeg_preset = 'GOOD'
ff.gopsize = fps
ff.audio_codec = 'NONE'
sc.render.filepath = out
sc.render.use_file_extension = False
bpy.ops.render.render(animation=True)
print('VIDEO', out, round(os.path.getsize(out) / 1e6, 1), 'MB', len(frames), 'frames', round(len(frames) / fps, 1), 's')
