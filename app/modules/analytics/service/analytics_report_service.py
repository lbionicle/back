from datetime import datetime
from io import BytesIO

import xlsxwriter

from app.modules.analytics.model.schemas import (
    AnalyticsPeriod,
    ServiceManagerAnalyticsRead,
)
from app.modules.tickets.model.models import TicketStatus

PRIMARY_COLOR = "#5F6FC8"
PRIMARY_DARK_COLOR = "#4856A8"
TEXT_COLOR = "#282B33"
MUTED_TEXT_COLOR = "#6B7280"
BORDER_COLOR = "#E5E7EB"
WHITE_COLOR = "#FFFFFF"

PERIOD_LABELS = {
    AnalyticsPeriod.week: "Неделя",
    AnalyticsPeriod.month: "Месяц",
    AnalyticsPeriod.three_months: "3 месяца",
    AnalyticsPeriod.six_months: "6 месяцев",
}

STATUS_LABELS = {
    TicketStatus.pending: "В ожидании",
    TicketStatus.in_progress: "В процессе",
    TicketStatus.closed: "Закрыт",
}

STATUS_COLORS = {
    TicketStatus.pending: "#A8B0E0",
    TicketStatus.in_progress: "#5F6FC8",
    TicketStatus.closed: "#4856A8",
}

RATING_COLORS = {
    1: "#DDE1F5",
    2: "#A8B0E0",
    3: "#5F6FC8",
    4: "#5362B5",
    5: "#4856A8",
}


def get_period_label(period: AnalyticsPeriod) -> str:
    return PERIOD_LABELS.get(period, period.value)


def get_status_label(status: TicketStatus) -> str:
    return STATUS_LABELS.get(status, status.value)


def get_status_color(status: TicketStatus) -> str:
    return STATUS_COLORS.get(status, PRIMARY_COLOR)


def get_rating_color(rating: int) -> str:
    return RATING_COLORS.get(rating, PRIMARY_COLOR)


def format_report_date() -> str:
    month_names = {
        1: "января",
        2: "февраля",
        3: "марта",
        4: "апреля",
        5: "мая",
        6: "июня",
        7: "июля",
        8: "августа",
        9: "сентября",
        10: "октября",
        11: "ноября",
        12: "декабря",
    }

    current_date = datetime.now()

    return (
        f"{current_date.day} {month_names[current_date.month]} "
        f"{current_date.year} г. в {current_date:%H:%M}"
    )


def parse_analytics_date(value: str) -> datetime:
    return datetime.fromisoformat(value)


def format_resolution_time(minutes: int | None) -> str:
    if minutes is None:
        return "Нет данных"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours == 0:
        return f"{remaining_minutes} мин"

    if remaining_minutes == 0:
        return f"{hours} ч"

    return f"{hours} ч {remaining_minutes} мин"


def format_rating(rating: float | None) -> str:
    if rating is None:
        return "Нет данных"

    return f"{rating:.1f} / 5"


def quote_sheet_name(sheet_name: str) -> str:
    return sheet_name.replace("'", "''")


def get_last_data_row(data_length: int) -> int:
    return data_length + 1


def get_major_unit(max_value: int | float | None) -> int | None:
    if max_value is None:
        return None

    if max_value <= 10:
        return 1

    return None


def build_formats(workbook: xlsxwriter.Workbook) -> dict[str, xlsxwriter.format.Format]:
    return {
        "title": workbook.add_format(
            {
                "bold": True,
                "font_size": 18,
                "font_color": TEXT_COLOR,
                "align": "left",
                "valign": "vcenter",
            },
        ),
        "section_title": workbook.add_format(
            {
                "bold": True,
                "font_size": 13,
                "font_color": TEXT_COLOR,
                "align": "left",
                "valign": "vcenter",
            },
        ),
        "label": workbook.add_format(
            {
                "bold": True,
                "font_color": TEXT_COLOR,
                "align": "left",
                "valign": "vcenter",
            },
        ),
        "plain": workbook.add_format(
            {
                "font_color": TEXT_COLOR,
                "align": "left",
                "valign": "vcenter",
            },
        ),
        "header": workbook.add_format(
            {
                "bold": True,
                "font_color": WHITE_COLOR,
                "bg_color": PRIMARY_COLOR,
                "border": 1,
                "border_color": BORDER_COLOR,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
            },
        ),
        "cell": workbook.add_format(
            {
                "font_color": TEXT_COLOR,
                "border": 1,
                "border_color": BORDER_COLOR,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
            },
        ),
        "cell_bold": workbook.add_format(
            {
                "bold": True,
                "font_color": TEXT_COLOR,
                "border": 1,
                "border_color": BORDER_COLOR,
                "align": "left",
                "valign": "vcenter",
                "text_wrap": True,
            },
        ),
        "date_cell": workbook.add_format(
            {
                "font_color": TEXT_COLOR,
                "border": 1,
                "border_color": BORDER_COLOR,
                "align": "left",
                "valign": "vcenter",
                "num_format": "dd.mm",
            },
        ),
        "number_cell": workbook.add_format(
            {
                "font_color": TEXT_COLOR,
                "border": 1,
                "border_color": BORDER_COLOR,
                "align": "left",
                "valign": "vcenter",
                "num_format": "0",
            },
        ),
    }


def setup_common_worksheet(worksheet) -> None:
    worksheet.hide_gridlines(2)
    worksheet.set_zoom(90)


def add_report_data_sheet(
    workbook: xlsxwriter.Workbook,
    analytics: ServiceManagerAnalyticsRead,
    period: AnalyticsPeriod,
    formats: dict[str, xlsxwriter.format.Format],
) -> None:
    worksheet = workbook.add_worksheet("Данные отчёта")
    setup_common_worksheet(worksheet)

    worksheet.set_column("A:A", 34)
    worksheet.set_column("B:B", 28)
    worksheet.set_column("C:C", 64)

    worksheet.write("A1", "Данные, использованные в отчёте", formats["title"])

    worksheet.write("A3", "Период", formats["label"])
    worksheet.write("B3", get_period_label(period), formats["plain"])

    worksheet.write("A4", "Дата формирования", formats["label"])
    worksheet.write("B4", format_report_date(), formats["plain"])

    worksheet.write("A6", "Ключевые показатели", formats["section_title"])

    worksheet.write_row(
        "A7",
        ["Показатель", "Значение", "Описание"],
        formats["header"],
    )

    rows = [
        [
            "Всего тикетов",
            str(analytics.summary.total_tickets_count),
            "Количество обращений, созданных за выбранный период",
        ],
        [
            "Среднее время решения",
            format_resolution_time(analytics.summary.average_resolution_minutes),
            "Среднее время от регистрации тикета до его закрытия",
        ],
        [
            "Средняя оценка качества",
            format_rating(analytics.summary.average_quality_rating),
            "Средняя пользовательская оценка по обработанным обращениям",
        ],
        [
            "Закрытые тикеты",
            str(analytics.summary.closed_tickets_count),
            "Количество тикетов, закрытых за выбранный период",
        ],
    ]

    start_row = 7

    for index, row in enumerate(rows, start=start_row):
        worksheet.write(index, 0, row[0], formats["cell_bold"])
        worksheet.write(index, 1, row[1], formats["cell"])
        worksheet.write(index, 2, row[2], formats["cell"])

    worksheet.freeze_panes(7, 0)


def add_created_tickets_sheet(
    workbook: xlsxwriter.Workbook,
    analytics: ServiceManagerAnalyticsRead,
    formats: dict[str, xlsxwriter.format.Format],
) -> None:
    worksheet = workbook.add_worksheet("Созданные тикеты")
    setup_common_worksheet(worksheet)

    worksheet.set_column("A:A", 20)
    worksheet.set_column("B:B", 32)

    worksheet.write_row(
        "A1",
        ["Дата", "Количество созданных тикетов"],
        formats["header"],
    )

    for index, point in enumerate(analytics.created_tickets_series, start=1):
        worksheet.write_datetime(
            index,
            0,
            parse_analytics_date(point.date),
            formats["date_cell"],
        )
        worksheet.write_number(index, 1, point.count, formats["number_cell"])

    worksheet.freeze_panes(1, 0)


def add_status_distribution_sheet(
    workbook: xlsxwriter.Workbook,
    analytics: ServiceManagerAnalyticsRead,
    formats: dict[str, xlsxwriter.format.Format],
) -> None:
    worksheet = workbook.add_worksheet("Статусы")
    setup_common_worksheet(worksheet)

    worksheet.set_column("A:A", 24)
    worksheet.set_column("B:B", 24)

    worksheet.write_row(
        "A1",
        ["Статус", "Количество тикетов"],
        formats["header"],
    )

    for index, point in enumerate(analytics.status_distribution, start=1):
        worksheet.write(index, 0, get_status_label(point.status), formats["cell"])
        worksheet.write_number(index, 1, point.count, formats["number_cell"])

    worksheet.freeze_panes(1, 0)


def add_resolution_time_sheet(
    workbook: xlsxwriter.Workbook,
    analytics: ServiceManagerAnalyticsRead,
    formats: dict[str, xlsxwriter.format.Format],
) -> None:
    worksheet = workbook.add_worksheet("Время решения")
    setup_common_worksheet(worksheet)

    worksheet.set_column("A:A", 20)
    worksheet.set_column("B:B", 30)
    worksheet.set_column("C:C", 30)

    worksheet.write_row(
        "A1",
        [
            "Дата",
            "Среднее время решения",
            "Среднее время решения, мин",
        ],
        formats["header"],
    )

    for index, point in enumerate(analytics.resolution_time_series, start=1):
        worksheet.write_datetime(
            index,
            0,
            parse_analytics_date(point.date),
            formats["date_cell"],
        )
        worksheet.write(
            index,
            1,
            format_resolution_time(point.average_resolution_minutes),
            formats["cell"],
        )

        if point.average_resolution_minutes is None:
            worksheet.write_blank(index, 2, None, formats["cell"])
        else:
            worksheet.write_number(
                index,
                2,
                point.average_resolution_minutes,
                formats["number_cell"],
            )

    worksheet.freeze_panes(1, 0)


def add_rating_distribution_sheet(
    workbook: xlsxwriter.Workbook,
    analytics: ServiceManagerAnalyticsRead,
    formats: dict[str, xlsxwriter.format.Format],
) -> None:
    worksheet = workbook.add_worksheet("Оценки")
    setup_common_worksheet(worksheet)

    worksheet.set_column("A:A", 18)
    worksheet.set_column("B:B", 24)

    worksheet.write_row(
        "A1",
        ["Оценка", "Количество оценок"],
        formats["header"],
    )

    for index, point in enumerate(analytics.rating_distribution, start=1):
        worksheet.write_number(index, 0, point.rating, formats["number_cell"])
        worksheet.write_number(index, 1, point.count, formats["number_cell"])

    worksheet.freeze_panes(1, 0)


def add_date_line_chart(
    workbook: xlsxwriter.Workbook,
    worksheet,
    *,
    source_sheet_name: str,
    title: str,
    y_axis_title: str,
    position: str,
    last_data_row: int,
    value_column: str,
    max_value: int | None,
) -> None:
    chart = workbook.add_chart({"type": "line"})

    value_column_index = ord(value_column.upper()) - ord("A")

    chart.add_series(
        {
            "name": title,
            "categories": [
                source_sheet_name,
                1,
                0,
                last_data_row - 1,
                0,
            ],
            "values": [
                source_sheet_name,
                1,
                value_column_index,
                last_data_row - 1,
                value_column_index,
            ],
            "line": {
                "color": PRIMARY_COLOR,
                "width": 2.25,
            },
            "marker": {
                "type": "circle",
                "size": 5,
                "border": {
                    "color": PRIMARY_COLOR,
                },
                "fill": {
                    "color": PRIMARY_COLOR,
                },
            },
        },
    )

    chart.set_title(
        {
            "name": title,
            "name_font": {
                "bold": True,
                "size": 12,
                "color": TEXT_COLOR,
            },
        },
    )

    chart.set_x_axis(
        {
            "name": "Дата",
            "date_axis": True,
            "num_format": "dd.mm",
            "name_font": {
                "color": MUTED_TEXT_COLOR,
            },
            "num_font": {
                "color": MUTED_TEXT_COLOR,
            },
            "major_tick_mark": "none",
        },
    )

    y_axis = {
        "name": y_axis_title,
        "min": 0,
        "name_font": {
            "color": MUTED_TEXT_COLOR,
        },
        "num_font": {
            "color": MUTED_TEXT_COLOR,
        },
        "major_gridlines": {
            "visible": True,
            "line": {
                "color": BORDER_COLOR,
            },
        },
    }

    major_unit = get_major_unit(max_value)

    if major_unit is not None:
        y_axis["major_unit"] = major_unit

    chart.set_y_axis(y_axis)

    chart.set_legend({"none": True})
    chart.set_size({"width": 520, "height": 300})
    chart.show_blanks_as("span")

    worksheet.insert_chart(position, chart)


def add_column_chart(
    workbook: xlsxwriter.Workbook,
    worksheet,
    *,
    source_sheet_name: str,
    title: str,
    x_axis_title: str,
    y_axis_title: str,
    position: str,
    last_data_row: int,
    point_colors: list[str],
    max_value: int | None,
) -> None:
    chart = workbook.add_chart({"type": "column"})

    safe_sheet_name = quote_sheet_name(source_sheet_name)

    chart.add_series(
        {
            "name": title,
            "categories": f"='{safe_sheet_name}'!$A$2:$A${last_data_row}",
            "values": f"='{safe_sheet_name}'!$B$2:$B${last_data_row}",
            "border": {
                "color": PRIMARY_DARK_COLOR,
            },
            "fill": {
                "color": PRIMARY_COLOR,
            },
            "points": [
                {
                    "fill": {
                        "color": color,
                    },
                    "border": {
                        "color": color,
                    },
                }
                for color in point_colors
            ],
        },
    )

    chart.set_title(
        {
            "name": title,
            "name_font": {
                "bold": True,
                "size": 12,
                "color": TEXT_COLOR,
            },
        },
    )

    chart.set_x_axis(
        {
            "name": x_axis_title,
            "name_font": {
                "color": MUTED_TEXT_COLOR,
            },
            "num_font": {
                "color": MUTED_TEXT_COLOR,
            },
            "major_tick_mark": "none",
        },
    )

    y_axis = {
        "name": y_axis_title,
        "min": 0,
        "name_font": {
            "color": MUTED_TEXT_COLOR,
        },
        "num_font": {
            "color": MUTED_TEXT_COLOR,
        },
        "major_gridlines": {
            "visible": True,
            "line": {
                "color": BORDER_COLOR,
            },
        },
    }

    major_unit = get_major_unit(max_value)

    if major_unit is not None:
        y_axis["major_unit"] = major_unit

    chart.set_y_axis(y_axis)

    chart.set_legend({"none": True})
    chart.set_size({"width": 520, "height": 300})

    worksheet.insert_chart(position, chart)


def add_charts_sheet(
    workbook: xlsxwriter.Workbook,
    analytics: ServiceManagerAnalyticsRead,
    formats: dict[str, xlsxwriter.format.Format],
) -> None:
    worksheet = workbook.add_worksheet("Графики")
    setup_common_worksheet(worksheet)

    worksheet.set_zoom(80)
    worksheet.set_column("A:O", 10)

    for row_index in range(0, 42):
        worksheet.set_row(row_index, 20)

    worksheet.write("A1", "Графики аналитики IntelliTicket", formats["title"])

    created_last_row = get_last_data_row(len(analytics.created_tickets_series))
    status_last_row = get_last_data_row(len(analytics.status_distribution))
    resolution_last_row = get_last_data_row(len(analytics.resolution_time_series))
    rating_last_row = get_last_data_row(len(analytics.rating_distribution))

    created_max_value = max(
        [point.count for point in analytics.created_tickets_series],
        default=0,
    )
    status_max_value = max(
        [point.count for point in analytics.status_distribution],
        default=0,
    )
    resolution_values = [
        point.average_resolution_minutes
        for point in analytics.resolution_time_series
        if point.average_resolution_minutes is not None
    ]
    resolution_max_value = max(resolution_values, default=0)
    rating_max_value = max(
        [point.count for point in analytics.rating_distribution],
        default=0,
    )

    add_date_line_chart(
        workbook=workbook,
        worksheet=worksheet,
        source_sheet_name="Созданные тикеты",
        title="Количество созданных тикетов",
        y_axis_title="Количество",
        position="A3",
        last_data_row=created_last_row,
        value_column="B",
        max_value=created_max_value,
    )

    add_column_chart(
        workbook=workbook,
        worksheet=worksheet,
        source_sheet_name="Оценки",
        title="Структура оценок пользователей",
        x_axis_title="Оценка",
        y_axis_title="Количество",
        position="I3",
        last_data_row=rating_last_row,
        point_colors=[
            get_rating_color(point.rating)
            for point in analytics.rating_distribution
        ],
        max_value=rating_max_value,
    )

    add_column_chart(
        workbook=workbook,
        worksheet=worksheet,
        source_sheet_name="Статусы",
        title="Распределение тикетов по статусам",
        x_axis_title="Статус",
        y_axis_title="Количество",
        position="A21",
        last_data_row=status_last_row,
        point_colors=[
            get_status_color(point.status)
            for point in analytics.status_distribution
        ],
        max_value=status_max_value,
    )

    add_date_line_chart(
        workbook=workbook,
        worksheet=worksheet,
        source_sheet_name="Время решения",
        title="Среднее время решения тикета",
        y_axis_title="Минуты",
        position="I21",
        last_data_row=resolution_last_row,
        value_column="C",
        max_value=resolution_max_value,
    )


def build_analytics_report_workbook(
    analytics: ServiceManagerAnalyticsRead,
    period: AnalyticsPeriod,
) -> BytesIO:
    output = BytesIO()

    workbook = xlsxwriter.Workbook(
        output,
        {
            "in_memory": True,
            "strings_to_numbers": False,
            "nan_inf_to_errors": True,
        },
    )

    workbook.set_properties(
        {
            "title": "Отчёт по аналитике IntelliTicket",
            "subject": "Аналитика тикет-сервиса",
            "author": "IntelliTicket",
            "company": "IntelliTicket",
        },
    )

    formats = build_formats(workbook)

    add_report_data_sheet(workbook, analytics, period, formats)
    add_charts_sheet(workbook, analytics, formats)
    add_created_tickets_sheet(workbook, analytics, formats)
    add_status_distribution_sheet(workbook, analytics, formats)
    add_resolution_time_sheet(workbook, analytics, formats)
    add_rating_distribution_sheet(workbook, analytics, formats)

    workbook.close()
    output.seek(0)

    return output