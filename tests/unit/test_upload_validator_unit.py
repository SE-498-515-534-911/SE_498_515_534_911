"""US-11 unit tests: upload validation (MLE-F-003, MLE-SR-003; SRS Table 4.2-1; SAD 4.3.3).

Boundary values come from Test Plan section 5: file size 9.9, 10 and 10.1 MB;
rows 19, 20, 50,000 and 50,001; columns 1, 2, 100 and 101.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from datasets.errors import ApiValidationError, PayloadTooLarge, UnsupportedMediaType
from datasets.validators import MAX_BYTES, MAX_COLS, MAX_ROWS, MIN_COLS, MIN_ROWS, validate_upload

MB = 1024 * 1024


def upload(content, name='data.csv', content_type='text/csv'):
    return SimpleUploadedFile(name, content, content_type=content_type)


def table(rows=20, cols=2):
    """A CSV with a header and ``rows`` data rows of ``cols`` columns."""
    header = ','.join(f'c{i}' for i in range(cols))
    line = ','.join(str(i) for i in range(cols))
    return (header + '\n' + (line + '\n') * rows).encode()


def csv_of_size(size):
    """A valid two-column CSV of exactly ``size`` bytes, within the row limit."""
    rows = 40_000
    head = b'id,text\n'
    width = (size - len(head)) // rows - 1  # bytes per row before '\n'
    lines = [f'{i},'.encode() for i in range(rows)]
    body = [line + b'x' * (width - len(line)) + b'\n' for line in lines]
    data = head + b''.join(body)
    data = data[:-1] + b'x' * (size - len(data)) + b'\n'
    assert len(data) == size
    return data


def message(exc_info):
    return exc_info.value.message


# ---- file type (415) ---------------------------------------------------------

@pytest.mark.parametrize('name', ['data.txt', 'data.csv.exe', 'data', 'data.xlsx'])
def test_non_csv_extension_is_415(name):
    with pytest.raises(UnsupportedMediaType) as exc:
        validate_upload(upload(table(), name=name))
    assert message(exc) == 'Only CSV files are supported.'
    assert exc.value.status == 415 and exc.value.field == 'file'


def test_extension_check_ignores_case():
    assert validate_upload(upload(table(), name='DATA.CSV')).rows == 20


@pytest.mark.parametrize('content_type', ['text/csv', 'text/plain', 'TEXT/CSV', 'text/csv; charset=utf-8'])
def test_accepted_content_types(content_type):
    assert validate_upload(upload(table(), content_type=content_type)).columns == 2


@pytest.mark.parametrize('content_type', ['application/json', 'image/png', ''])
def test_other_content_types_are_415(content_type):
    with pytest.raises(UnsupportedMediaType):
        validate_upload(upload(table(), content_type=content_type))


def test_excel_content_type_from_windows_browsers_is_refused():
    """Observation O-1: browsers on Windows with Excel installed often send
    application/vnd.ms-excel for .csv files. This pins the current behaviour."""
    with pytest.raises(UnsupportedMediaType):
        validate_upload(upload(table(), content_type='application/vnd.ms-excel'))


# ---- size (413) and empty file -----------------------------------------------

@pytest.mark.parametrize('size', [int(9.9 * MB), 10 * MB])
def test_files_up_to_exactly_10_mb_are_accepted(size):
    assert MAX_BYTES == 10 * MB
    info = validate_upload(upload(csv_of_size(size)))
    assert info.rows == 40_000


@pytest.mark.parametrize('size', [10 * MB + 1, int(10.1 * MB)])
def test_files_over_10_mb_are_413(size):
    with pytest.raises(PayloadTooLarge) as exc:
        validate_upload(upload(b'x' * size))
    assert message(exc) == 'The file is larger than 10 MB.'
    assert exc.value.status == 413


def test_empty_file_is_400():
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(b''))
    assert message(exc) == 'The file is empty.'


# ---- encoding ----------------------------------------------------------------

def test_non_utf8_file_is_refused():
    content = 'name,city\n' + 'Zoë,Köln\n' * 20
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(content.encode('latin-1')))
    assert message(exc) == 'The file must be UTF-8 encoded.'


def test_utf8_with_bom_is_accepted_and_bom_is_not_in_the_header():
    info = validate_upload(upload(b'\xef\xbb\xbf' + table()))
    assert info.header == ['c0', 'c1']


def test_file_can_be_read_again_after_validation():
    uploaded = upload(table())
    validate_upload(uploaded)
    assert uploaded.read() == table()


# ---- header ------------------------------------------------------------------

def test_file_with_only_blank_lines_has_no_header():
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(b'\n\n\n'))
    assert message(exc) == 'The file has no header row.'


def test_empty_header_name_is_refused():
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(b'a,,c\n' + b'1,2,3\n' * 20))
    assert message(exc) == 'Header names must not be empty.'


def test_numeric_first_row_is_not_a_header():
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(b'1,2.5,-3\n' + b'1,2,3\n' * 20))
    assert 'must be a header row' in message(exc)


def test_header_with_some_numbers_is_accepted():
    assert validate_upload(upload(b'2024,sales\n' + b'1,2\n' * 20)).header == ['2024', 'sales']


def test_duplicate_header_names_are_refused():
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(b'a,b,a\n' + b'1,2,3\n' * 20))
    assert message(exc) == 'Header names must be unique.'


def test_header_names_are_trimmed():
    assert validate_upload(upload(b' a , b \n' + b'1,2\n' * 20)).header == ['a', 'b']


# ---- columns -----------------------------------------------------------------

@pytest.mark.parametrize('cols', [MIN_COLS, MAX_COLS])
def test_column_count_on_the_boundaries_is_accepted(cols):
    assert (MIN_COLS, MAX_COLS) == (2, 100)
    assert validate_upload(upload(table(cols=cols))).columns == cols


@pytest.mark.parametrize('cols', [MIN_COLS - 1, MAX_COLS + 1])
def test_column_count_just_outside_is_refused(cols):
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(table(cols=cols)))
    assert message(exc) == f'The file must have 2 to 100 columns (found {cols}).'


def test_row_with_wrong_number_of_fields_names_the_line():
    content = table(rows=20).replace(b'0,1\n', b'0,1,2\n', 1)
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(content))
    assert message(exc) == 'Row 2 has 3 fields but the header has 2.'


# ---- rows --------------------------------------------------------------------

@pytest.mark.parametrize('rows', [MIN_ROWS, MAX_ROWS])
def test_row_count_on_the_boundaries_is_accepted(rows):
    assert (MIN_ROWS, MAX_ROWS) == (20, 50_000)
    assert validate_upload(upload(table(rows=rows))).rows == rows


def test_19_rows_is_refused():
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(table(rows=MIN_ROWS - 1)))
    assert message(exc) == 'The file needs at least 20 data rows (found 19).'


def test_50001_rows_is_refused():
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(table(rows=MAX_ROWS + 1)))
    assert message(exc) == 'The file has more than 50,000 data rows.'


def test_blank_lines_are_not_counted_as_rows():
    content = b'a,b\n' + b'1,2\n\n' * 20
    assert validate_upload(upload(content)).rows == 20


def test_csv_syntax_error_is_reported_as_invalid_csv():
    huge_field = b'"' + b'x' * 200_000 + b'"'
    content = b'a,b\n' + huge_field + b',1\n' + b'1,2\n' * 20
    with pytest.raises(ApiValidationError) as exc:
        validate_upload(upload(content))
    assert message(exc) == 'The file is not a valid CSV file.'


def test_valid_file_returns_its_shape():
    info = validate_upload(upload(b'age,city,score\n' + b'20,Pune,1.5\n' * 25))
    assert (info.header, info.rows, info.columns) == (['age', 'city', 'score'], 25, 3)
