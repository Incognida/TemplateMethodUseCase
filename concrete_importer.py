import csv
from django.utils import timezone
from xlrd import open_workbook
from .models import HandleStatus
from .importer import ImportFile


class ImportExcel(ImportFile):
    def run(self, encoding):
        flag = False
        try:
            rb = open_workbook(self._obj.file.path, encoding_override=encoding)
        except Exception:
            flag = True
        if flag:
            try:
                rb = open_workbook(self._obj.file.path, encoding_override='cp1251')
            except Exception:
                flag = 'impossible'
            if flag == 'impossible':
                self._obj.error_string += 'Не удалось прочесть файл. Разрешенные форматы:' \
                                          'xls, xlsx, csv. Проверьте кол-во' \
                                          'строк. Если строк больше 16 тысяч,' \
                                          ' используйте формат csv'
                self._obj.import_status = HandleStatus.ERROR
                self._obj.finished_at = timezone.now()
                self._obj.save()
                return False

        if not rb.sheets():
            self._obj.error_string += "Не удалось прочесть файл, проверьте" \
                                "формат файла. Разрешенные форматы: xls, xlsx, csv"
            self._obj.import_status = HandleStatus.ERROR
            self._obj.finished_at = timezone.now()
            self._obj.save()
            return False

        sh = rb.sheet_by_index(0)
        row_size = sh.nrows
        col_size = sh.ncols
        if row_size <= 1 or col_size == 0 or col_size > 2:
            self._obj.error_string += "Некорректно заполнены данные"
            self._obj.import_status = HandleStatus.ERROR
            self._obj.finished_at = timezone.now()
            self._obj.save()
            return False

        self._obj.import_status = HandleStatus.PROCESSING
        for i in range(1, row_size):
            cleaned_number = None
            if col_size == 2:
                raw_icc = sh.col_values(0, start_rowx=i, end_rowx=i + 1)
                raw_phone_number = sh.col_values(1, start_rowx=i, end_rowx=i + 1)
                cleaned_icc = self._obj.clean_excel_number(str(raw_icc[0]))
                cleaned_number = self._obj.clean_excel_number(str(raw_phone_number[0]))
            else:
                raw_icc = sh.col_values(0, start_rowx=i, end_rowx=i + 1)
                cleaned_icc = self._obj.clean_excel_number(str(raw_icc[0]))
            self._handle_line(cleaned_icc, cleaned_number, i)


class ImportCsv(ImportFile):
    def detect_delimiter_encoding(self, encoding):
        try:
            with open(self._obj.file.path, 'r', encoding=encoding) as f:
                f.read(4)
        except UnicodeDecodeError:
            encoding = 'cp1251'

        with open(self._obj.file.path, 'r', encoding=encoding) as f:
            print('encoding: ' + str(encoding))
            header = f.readline()
            if header.find(";") != -1:
                return ";", encoding
            if header.find(",") != -1:
                return ",", encoding
        return ";", encoding

    def run(self, encoding):
        delimiter, encoding = self.detect_delimiter_encoding(encoding=encoding)
        with open(self._obj.file.path, encoding=encoding) as f:
            datareader = csv.reader(f, delimiter=delimiter)
            self._obj.import_status = HandleStatus.PROCESSING
            for i, row in enumerate(datareader):
                if i == 0:
                    continue
                if len(row) == 1:
                    cleaned_icc = row[0]
                    cleaned_number = False
                else:
                    cleaned_icc = row[0]
                    cleaned_number = row[1]
                    if cleaned_number == ' ' or cleaned_number == '':
                        cleaned_number = False
                    if cleaned_icc == ' ' or cleaned_icc == '':
                        cleaned_icc = False
                # На всякий случай
                if cleaned_icc and ('E+' in cleaned_icc):
                    self.mat_counter += 1
                    self.mat_errors.append((i + 1, ["Поставьте знак ' перед ICC"]))
                    continue
                self._handle_line(cleaned_icc, cleaned_number, i)
