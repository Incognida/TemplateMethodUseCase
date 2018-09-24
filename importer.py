from abc import ABCMeta, abstractmethod
from django.utils import timezone
from django.db.utils import IntegrityError
from .models import Simcard, HandleStatus
from .tools import CustomValidator


class ImportFile(metaclass=ABCMeta):
    def __init__(self, obj):
        self._obj = obj
        self.success_counter = 0
        self.soft_error_counter = 0
        self.crime_counter = 0
        self.empty_counter = 0
        self.mat_counter = 0
        self.result_list_soft_errors = []
        self.result_list_crime_errors = []
        self.mat_errors = []

    def _handle_line(self, cleaned_icc, cleaned_number, line_number):
        list_soft_errors = []
        list_crime_errors = []
        other_dealer_sim = False

        if cleaned_icc and cleaned_number:
            # If phone_number
            phone_number, soft_error = CustomValidator. \
                validate_phone_number(cleaned_number)
            if soft_error:
                self.soft_error_counter += 1
                list_soft_errors.append(
                    "Невалидный номер телефона ({})".format(cleaned_number)
                )
            # If cleaned icc
            icc, soft_error = CustomValidator.validate_text(cleaned_icc, icc=True)
            if soft_error:
                self.soft_error_counter += 1
                list_soft_errors.append(
                    "Невалидный ICC ({})".format(cleaned_icc)
                )

            else:
                other_dealer_sim = Simcard.objects.exclude(
                    dealer=self._obj.dealer).filter(icc_id=icc).exists()
                if not other_dealer_sim:
                    other_dealer_sim = Simcard.objects.exclude(
                        dealer=self._obj.dealer).filter(icc_id=icc[:-1]).exists()

                if icc and other_dealer_sim:
                    self.crime_counter += 1
                    list_crime_errors.append(
                        "ICC с номером ({}) в базе уже существует".format(icc)
                    )
                    crime_msg = "Дилер-{0}-{1}, пытался загрузить в базу СИМ с уже существующем ICC"
                    # TODO: отправить мейл мессадж админу

            if icc and phone_number and not other_dealer_sim:
                same_sim = Simcard.objects.filter(
                    dealer=self._obj.dealer,
                    icc_id=icc
                ).first()
                if not same_sim:
                    same_sim = Simcard.objects.filter(
                        dealer=self._obj.dealer,
                        icc_id=icc[:-1]
                    ).first()
                if same_sim:
                    if not same_sim.sold:
                        if phone_number in same_sim.number_list:
                            self.soft_error_counter += 1
                            list_soft_errors.append(
                                'СИМ с таким же'
                                ' ICC ({0})'
                                ' и номером ({1}) существует'.format(icc, phone_number)
                            )
                        else:
                            same_sim.number_list.append(phone_number)
                            same_sim.save()
                            self.success_counter += 1
                    else:
                        self.soft_error_counter += 1
                        list_soft_errors.append(
                            'СИМ с таким же ICC ({0}) уже продана'.format(icc)
                        )
                else:
                    try:
                        Simcard.objects.create(
                            dealer=self._obj.dealer,
                            icc_id=icc, number_list=[phone_number]
                        )
                        self.success_counter += 1
                    except IntegrityError:
                        pass
        elif cleaned_icc:
            icc, soft_error = CustomValidator.validate_text(cleaned_icc, icc=True)
            if soft_error:
                self.soft_error_counter += 1
                list_soft_errors.append(
                    "Невалидный ICC ({})".format(cleaned_icc)
                )
            else:
                other_dealer_sim = Simcard.objects.exclude(
                    dealer=self._obj.dealer).filter(icc_id=icc).exists()
                if not other_dealer_sim:
                    other_dealer_sim = Simcard.objects.exclude(
                        dealer=self._obj.dealer).filter(icc_id=icc[:-1]).exists()

                if icc and other_dealer_sim:
                    self.crime_counter += 1
                    list_crime_errors.append(
                        "ICC с номером ({}) в базе уже существует".format(icc)
                    )
                    crime_msg = "Дилер-{0}-{1}, пытался загрузить в базу СИМ с уже существующем ICC"

            if icc and not other_dealer_sim:
                same_sim = Simcard.objects.filter(
                    dealer=self._obj.dealer,
                    icc_id=icc
                ).first()
                if not same_sim:
                    same_sim = Simcard.objects.filter(
                        dealer=self._obj.dealer,
                        icc_id=icc[:-1]
                    ).first()

                if same_sim and same_sim.sold:
                    self.soft_error_counter += 1
                    list_soft_errors.append(
                        'СИМ с таким же ICC ({}) уже продана'.format(icc)
                    )
                elif same_sim:
                    self.soft_error_counter += 1
                    list_soft_errors.append(
                        'СИМ с таким же ICC ({}) уже существует'.format(icc)
                    )
                else:
                    try:
                        Simcard.objects.create(dealer=self._obj.dealer, icc_id=icc)
                        self.success_counter += 1
                    except IntegrityError:
                        pass
        elif cleaned_number:
            self.soft_error_counter += 1
            list_soft_errors.append('Пустой ICC')

            phone_number, soft_error = CustomValidator. \
                validate_phone_number(cleaned_number)
            if soft_error:
                self.soft_error_counter += 1
                list_soft_errors.append(
                    "Невалидный номер телефона ({})".format(cleaned_number)
                )
        else:
            self.empty_counter += 1
            self.soft_error_counter += 1
            list_soft_errors.append('Пустая строка')

        if list_soft_errors:
            self.result_list_soft_errors.append((line_number + 1, list_soft_errors))
        if list_crime_errors:
            self.result_list_crime_errors.append((line_number + 1, list_crime_errors))
        return 0

    def gather_errors(self):
        self._obj.error_string += self._obj.result_string(
            self.result_list_soft_errors, self.result_list_crime_errors,
            self.mat_errors,
            self.success_counter, self.empty_counter,
            self.soft_error_counter, self.crime_counter,
            self.mat_counter
        )
        self._obj.import_status = HandleStatus.DONE
        self._obj.finished_at = timezone.now()
        self._obj.save()
        return 0

    @abstractmethod
    def run(self, encoding):
        pass

