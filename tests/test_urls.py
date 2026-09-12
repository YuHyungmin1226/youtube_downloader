import unittest

from utils import validate_url


class URLValidationTests(unittest.TestCase):
    def test_supported_video_links_normalize(self):
        for url in (
            'youtu.be/dQw4w9WgXcQ',
            'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://music.youtube.com/watch?v=dQw4w9WgXcQ',
            'HTTPS://WWW.YOUTUBE.COM/watch?v=dQw4w9WgXcQ',
            'https://www.youtube.com/shorts/dQw4w9WgXcQ',
            'https://www.youtube.com/embed/dQw4w9WgXcQ',
            'https://www.youtube.com/live/dQw4w9WgXcQ',
        ):
            with self.subTest(url=url):
                self.assertEqual(validate_url(url), (
                    True, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                ))

    def test_playlist_and_index_are_preserved(self):
        for path in ('playlist?list=PL_123-abc', 'watch?v=dQw4w9WgXcQ&list=PL_123-abc'):
            url = f'https://www.youtube.com/{path}&index=2'
            with self.subTest(url=url):
                self.assertEqual(validate_url(url), (True, url))
        self.assertEqual(
            validate_url('https://youtu.be/dQw4w9WgXcQ?list=PL_123-abc&index=2'),
            (True, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL_123-abc&index=2'),
        )

    def test_invalid_video_ids_and_unrelated_paths_are_rejected(self):
        for path in (
            'watch?v=dQw4w9WgXcQEXTRA',
            'watch?v=dQw4w9WgXc',
            'watch?other=dQw4w9WgXcQ',
            'watch?v=&list=PL123',
            'playlist',
            'playlist?list=',
            'playlist?list=invalid%2Fid',
            '@abcdefghijk',
            'anything/dQw4w9WgXcQ',
            'shorts/dQw4w9WgXcQEXTRA',
        ):
            with self.subTest(path=path):
                self.assertFalse(validate_url(f'https://www.youtube.com/{path}')[0])
        self.assertFalse(validate_url('https://youtu.be/dQw4w9WgXcQEXTRA')[0])

    def test_host_impersonation_and_invalid_authorities_are_rejected(self):
        for host in (
            'youtube.com.evil.example', 'evilyoutube.com',
            'youtube.com@evil.example', 'evil.example@youtube.com',
            'youtube.com:invalid', '[youtube.com',
        ):
            with self.subTest(host=host):
                self.assertFalse(validate_url(f'https://{host}/watch?v=dQw4w9WgXcQ')[0])
        self.assertFalse(validate_url('ftp://youtube.com/watch?v=dQw4w9WgXcQ')[0])

    def test_invalid_index_is_omitted(self):
        for index in ('0', '-1', 'abc'):
            with self.subTest(index=index):
                self.assertEqual(
                    validate_url(f'https://youtube.com/playlist?list=PL123&index={index}'),
                    (True, 'https://www.youtube.com/playlist?list=PL123'),
                )

    def test_other_supported_site_is_preserved(self):
        url = 'https://www.pornhub.com/view_video.php?viewkey=example'
        self.assertEqual(validate_url(url), (True, url))


if __name__ == '__main__':
    unittest.main()
