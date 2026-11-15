# SPDX-License-Identifier: AGPL-3.0-only
"""Trộn thư ▸ Chọn người nhận ▸ Chọn từ danh bạ: a data source already registered in the office (an address book
set up with Công cụ ▸ Nguồn sổ địa chỉ, a database file, ...). The document stores it as "danhba:<source>\\t<table>";
its rows are read through SDBC into a mail_merge_table.Table (numbers and dates keep their type)."""
from . import mail_merge_format as fmt
from . import mail_merge_table as mt

PREFIX = "danhba:"
HIDDEN = ("HST_TronThu_", "Bibliography")  # our own staging copies and the sample bibliography
MAX_ROWS = 20000
NUMBER_TYPES = {-7, -6, -5, 2, 3, 4, 5, 6, 7, 8, 16}  # com.sun.star.sdbc.DataType: BIT..DOUBLE, BOOLEAN
DATE_TYPES = {91, 93}  # DATE, TIMESTAMP


def encode(source, table):
    return "%s%s\t%s" % (PREFIX, source, table)


def decode(text):
    source, _, table = text[len(PREFIX):].partition("\t")
    return source, table


def label(text):
    source, table = decode(text)
    return "%s – %s" % (source, table)


def _context(ctx):
    return ctx.ServiceManager.createInstanceWithContext("com.sun.star.sdb.DatabaseContext", ctx)


def entries(ctx):
    """[(source, table)] of every registered data source the user can pick (tables, then queries)."""
    found = []
    context = _context(ctx)
    for name in context.ElementNames:
        if name.startswith(HIDDEN):
            continue
        connection = None
        try:
            source = context.getByName(name)
            connection = source.getConnection("", "")
            names = list(connection.Tables.ElementNames)
            try:
                names += [q for q in connection.Queries.ElementNames if q not in names]
            except Exception:  # noqa: BLE001 - a driver without queries
                pass
            found += [(name, table) for table in names]
        except Exception:  # noqa: BLE001 - a source that cannot connect (missing file, password) is not offered
            continue
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:  # noqa: BLE001
                    pass
    return found


def _cell(result, index, kind):
    if kind == fmt.COL_NUMBER:
        value = result.getDouble(index)
        return None if result.wasNull() else float(value)
    if kind == fmt.COL_DATE:
        value = result.getDate(index)
        if result.wasNull() or not value.Year:
            return None
        import datetime
        return float((datetime.date(value.Year, value.Month, value.Day) - fmt.NULL_DATE).days)
    value = result.getString(index)
    return None if result.wasNull() or value == "" else value


def read(ctx, text):
    """Table of the address book stored as `text`. Raises mail_merge_source.SourceError("missing") when gone."""
    from .mail_merge_source import SourceError
    source, table = decode(text)
    rowset = ctx.ServiceManager.createInstanceWithContext("com.sun.star.sdb.RowSet", ctx)
    try:
        rowset.DataSourceName, rowset.Command, rowset.CommandType = source, table, 0
        try:
            rowset.execute()
        except Exception:  # noqa: BLE001 - a query, not a table
            rowset.CommandType = 1
            rowset.execute()
        meta = rowset.getMetaData()
        count = meta.getColumnCount()
        headers = mt.clean_headers([meta.getColumnLabel(i) for i in range(1, count + 1)])
        kinds = [fmt.COL_NUMBER if meta.getColumnType(i) in NUMBER_TYPES else
                 fmt.COL_DATE if meta.getColumnType(i) in DATE_TYPES else fmt.COL_TEXT for i in range(1, count + 1)]
        rows = []
        while rowset.next() and len(rows) < MAX_ROWS:
            rows.append(tuple(_cell(rowset, i + 1, kinds[i]) for i in range(count)))
    except SourceError:
        raise
    except Exception as exc:  # noqa: BLE001 - source removed, file gone, password needed
        raise SourceError("missing", label(text)) from exc
    finally:
        try:
            rowset.dispose()
        except Exception:  # noqa: BLE001
            pass
    if not rows:
        raise SourceError("empty")
    return mt.Table(headers, kinds, [tuple(r) for r in rows])
