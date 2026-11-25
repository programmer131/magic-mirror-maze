import tempfile
import unittest
from pathlib import Path

from magic_mirror.pose_track import CameraStream, camera_sources


class CameraSourcesTests(unittest.TestCase):
    def test_auto_prefers_stable_usb_video_capture_link(self):
        with tempfile.TemporaryDirectory() as root:
            dev = Path(root)
            (dev / 'video1').touch()
            (dev / 'video2').touch()
            by_id = dev / 'v4l' / 'by-id'
            by_id.mkdir(parents=True)
            (by_id / 'usb-camera-video-index0').symlink_to('../../video1')
            (by_id / 'usb-camera-video-index1').symlink_to('../../video2')
            sources = camera_sources(None, dev)
            self.assertEqual(sources[0], str(by_id / 'usb-camera-video-index0'))
            self.assertNotIn(str(by_id / 'usb-camera-video-index1'), sources)

    def test_explicit_camera_does_not_switch_to_another_device(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(camera_sources(3, Path(root)), [str(Path(root) / 'video3')])

    def test_stream_reopens_after_disconnection(self):
        class FakeCapture:
            def __init__(self, result):
                self.result = result
                self.released = False

            def read(self):
                return self.result

            def release(self):
                self.released = True

        failed = FakeCapture((False, None))
        recovered = FakeCapture((True, 'frame'))
        captures = iter([failed, recovered])
        stream = CameraStream(lambda: next(captures))
        self.assertEqual(stream.read(), (False, None))
        self.assertTrue(failed.released)
        self.assertEqual(stream.generation, 1)
        self.assertEqual(stream.read(), (True, 'frame'))
        self.assertEqual(stream.generation, 2)
        stream.close()
        self.assertTrue(recovered.released)


if __name__ == '__main__':
    unittest.main()
