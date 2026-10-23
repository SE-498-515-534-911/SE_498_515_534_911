from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from datasets.errors import ApiValidationError, PayloadTooLarge, UnsupportedMediaType
from datasets.validators import MAX_BYTES, validate_upload


def make_csv(rows=20, cols=3, header=None):
    header = header or ",".join(f"col{i}" for i in range(cols))
    lines = [header] + [",".join(str(r + c) for c in range(cols)) for r in range(rows)]
    return ("\n".join(lines) + "\n").encode()


def up(data, name="data.csv", mime="text/csv"):
    return SimpleUploadedFile(name, data, content_type=mime)


class ValidateUploadTests(SimpleTestCase):
    def test_valid_file(self):
        info = validate_upload(up(make_csv(20, 3)))
        self.assertEqual((info.rows, info.columns), (20, 3))

    def test_exactly_20_rows_accepted_and_19_rejected(self):
        validate_upload(up(make_csv(20)))
        with self.assertRaises(ApiValidationError):
            validate_upload(up(make_csv(19)))

    def test_wrong_extension_415(self):
        with self.assertRaises(UnsupportedMediaType):
            validate_upload(up(make_csv(), name="notes.txt", mime="text/plain"))

    def test_wrong_mime_415(self):
        with self.assertRaises(UnsupportedMediaType):
            validate_upload(up(make_csv(), mime="image/png"))

    def test_text_plain_accepted(self):
        validate_upload(up(make_csv(), mime="text/plain"))

    def test_over_10mb_413(self):
        with self.assertRaises(PayloadTooLarge):
            validate_upload(up(b"a" * (MAX_BYTES + 1)))

    def test_exactly_10mb_accepted(self):
        row = b"x," + b"y" * 250 + b"\n"
        header = b"a,b\n"
        k = (MAX_BYTES - len(header)) // len(row)
        extra = MAX_BYTES - len(header) - k * len(row)      # spread the remainder in the last row
        data = header + row * (k - 1) + b"x," + b"y" * (250 + extra) + b"\n"
        self.assertEqual(len(data), MAX_BYTES)
        self.assertEqual(validate_upload(up(data)).columns, 2)

    def test_empty_400(self):
        with self.assertRaises(ApiValidationError):
            validate_upload(up(b""))

    def test_no_header_400(self):
        data = "\n".join(f"{i},{i+1}" for i in range(30)).encode()
        with self.assertRaises(ApiValidationError):
            validate_upload(up(data))

    def test_one_column_400(self):
        with self.assertRaises(ApiValidationError):
            validate_upload(up(make_csv(20, 1)))

    def test_101_columns_400_and_100_ok(self):
        validate_upload(up(make_csv(20, 100)))
        with self.assertRaises(ApiValidationError):
            validate_upload(up(make_csv(20, 101)))

    def test_inconsistent_row_400(self):
        data = make_csv(25, 3) + b"1,2\n"
        with self.assertRaises(ApiValidationError):
            validate_upload(up(data))

    def test_duplicate_header_400(self):
        with self.assertRaises(ApiValidationError):
            validate_upload(up(make_csv(20, 2, header="a,a")))

    def test_empty_header_name_400(self):
        with self.assertRaises(ApiValidationError):
            validate_upload(up(make_csv(20, 2, header="a,")))

    def test_non_utf8_400(self):
        data = make_csv(20, 2).replace(b"col0", b"\xff\xfe")
        with self.assertRaises(ApiValidationError):
            validate_upload(up(data))

    def test_utf8_bom_accepted(self):
        validate_upload(up(b"\xef\xbb\xbf" + make_csv(20, 2)))

    def test_blank_lines_ignored(self):
        validate_upload(up(make_csv(20, 2) + b"\n\n"))


    def test_formula_like_values_are_treated_as_data(self):
        rows = ["=1+1,+value,-value,@value"]
        rows.extend("ordinary,value,ordinary,value" for _ in range(19))
        data = ("col1,col2,col3,col4\n" + "\n".join(rows) + "\n").encode()

        info = validate_upload(up(data))
        self.assertEqual((info.rows, info.columns), (20, 4))
