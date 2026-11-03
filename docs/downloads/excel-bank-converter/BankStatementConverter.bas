Attribute VB_Name = "BankStatementConverter"
Option Explicit

'Windows desktop Excel. No added VBA references required.
'Entry point: ConvertBankStatement. The selected source is never saved.
Public Sub ConvertBankStatement()
    Dim sourcePath As Variant, wb As Workbook, ws As Worksheet, fd As Object
    Dim oldSecurity As Long, oldScreen As Boolean, oldEvents As Boolean
    Dim header As Long, cols(1 To 7) As Long, i As Long, j As Long, lastRow As Long
    Dim data As Collection, notes As Collection, rec As Variant, prior As Variant
    Dim dt As Date, vd As Date, debit As Currency, credit As Currency, bal As Currency
    Dim opening As Currency, closing As Currency, running As Currency, movement As Currency
    Dim root As String, folder As String, key As Variant, groups As Object, group As Collection
    Dim missingNarration As Long, missingReference As Long, summary As Collection, reverse As Collection
    Dim message As String, reversed As Boolean, excluded As Long, headerFound As Boolean
    oldSecurity = Application.AutomationSecurity
    oldScreen = Application.ScreenUpdating: oldEvents = Application.EnableEvents
    On Error GoTo Failed
    sourcePath = Application.GetOpenFilename("Excel statements (*.xls;*.xlsx),*.xls;*.xlsx", , "Choose original bank statement")
    If VarType(sourcePath) = vbBoolean Then Exit Sub
    Application.AutomationSecurity = 3 'Never run macros in the source workbook.
    Application.EnableEvents = False: Application.ScreenUpdating = False
    Set wb = Workbooks.Open(Filename:=CStr(sourcePath), UpdateLinks:=0, ReadOnly:=True, AddToMru:=False)
    Application.AutomationSecurity = oldSecurity
    For Each ws In wb.Worksheets
        If FindHeader(ws, header, cols) Then
            headerFound = True: Exit For
        End If
    Next ws
    If Not headerFound Then Err.Raise vbObjectError + 101, , "Required columns not found: Date, Withdrawal/Debit, Deposit/Credit and Closing/Running Balance. This converter expects the HDFC table layout."
    Set data = New Collection: Set notes = New Collection
    lastRow = ws.UsedRange.Row + ws.UsedRange.Rows.Count - 1
    For i = header + 1 To lastRow
        message = UCase$(Trim$(CStr(ws.Cells(i, cols(1)).Value2)))
        If InStr(message, "STATEMENT SUMMARY") > 0 Or InStr(message, "END OF STATEMENT") > 0 Then Exit For
        If ReadDate(ws.Cells(i, cols(1)), dt) Then
            debit = ReadMoney(ws.Cells(i, cols(5)), True)
            credit = ReadMoney(ws.Cells(i, cols(6)), True)
            bal = ReadMoney(ws.Cells(i, cols(7)), False)
            If debit <> 0 And credit <> 0 Then Err.Raise vbObjectError + 102, , "Source row " & i & ": both withdrawal and deposit have values. Review this row."
            movement = credit - debit
            If movement = 0 Then Err.Raise vbObjectError + 103, , "Source row " & i & ": zero transaction. Review this row."
            vd = dt
            If cols(2) > 0 Then
                If Len(Trim$(CStr(ws.Cells(i, cols(2)).Value2))) > 0 Then
                    If Not ReadDate(ws.Cells(i, cols(2)), vd) Then Err.Raise vbObjectError + 104, , "Source row " & i & ": invalid value date."
                End If
            End If
            rec = Array(Format$(dt, "yyyy-mm-dd"), Format$(vd, "yyyy-mm-dd"), CellText(ws, i, cols(3)), CellText(ws, i, cols(4)), IIf(movement < 0, -movement, CCur(0)), IIf(movement > 0, movement, CCur(0)), bal, i)
            If debit < 0 Or credit < 0 Then notes.Add "Source row " & i & ": withdrawal " & Money(debit) & ", deposit " & Money(credit) & " normalised to debit " & Money(CCur(rec(4))) & ", credit " & Money(CCur(rec(5))) & ". Net movement unchanged."
            If rec(2) = "" Then missingNarration = missingNarration + 1
            If rec(3) = "" Then missingReference = missingReference + 1
            data.Add rec
            If data.Count > 50000 Then Err.Raise vbObjectError + 105, , "More than 50,000 transactions. Split the source statement."
        Else
            'Page headings and separators are harmless; financial rows with bad dates are not.
            If HasAmount(ws.Cells(i, cols(5))) Or HasAmount(ws.Cells(i, cols(6))) Then
                Err.Raise vbObjectError + 106, , "Source row " & i & ": amount present but transaction date is invalid. Nothing exported."
            End If
            excluded = excluded + 1
        End If
    Next i
    If data.Count = 0 Then Err.Raise vbObjectError + 107, , "No transaction rows found."
    'Try source order first; try the exact reverse only if source order fails.
    If Not CheckRows(data, opening, closing, message) Then
        Set reverse = New Collection
        For i = data.Count To 1 Step -1: reverse.Add data(i): Next i
        If Not CheckRows(reverse, opening, closing, message) Then Err.Raise vbObjectError + 108, , message & " Nothing exported."
        Set data = reverse: reversed = True
    End If
    wb.Close SaveChanges:=False: Set wb = Nothing
    Set fd = Application.FileDialog(4): fd.Title = "Choose a folder for converted CSV files"
    If fd.Show <> -1 Then GoTo CleanUp
    root = fd.SelectedItems(1)
    folder = root & Application.PathSeparator & "Yathartha-Bank-Import-" & Format$(Now, "yyyymmdd-hhnnss")
    If Len(Dir$(folder, vbDirectory)) > 0 Then Err.Raise vbObjectError + 109, , "Output folder already exists. Run again after a few seconds."
    MkDir folder
    Set groups = CreateObject("Scripting.Dictionary")
    For i = 1 To data.Count
        rec = data(i): key = Left$(CStr(rec(0)), 7)
        If Not groups.Exists(key) Then
            Set group = New Collection: groups.Add key, group
        End If
        Set group = groups(key): group.Add rec
    Next i
    Set summary = New Collection
    summary.Add "file,statement_from,statement_through,transactions,opening_INR,closing_INR"
    WriteTransactions folder & "\Bank-Combined.csv", data
    summary.Add SummaryLine("Bank-Combined.csv", data)
    For Each key In groups.Keys
        Set group = groups(key)
        WriteTransactions folder & "\Bank-" & key & ".csv", group
        summary.Add SummaryLine("Bank-" & key & ".csv", group)
    Next key
    WriteLines folder & "\Import-balances.csv", summary
    Dim help As Collection: Set help = New Collection
    help.Add "Yathartha bank statement conversion"
    help.Add "Source: " & CStr(sourcePath)
    help.Add "Transactions: " & data.Count & "; missing narration: " & missingNarration & "; missing reference: " & missingReference
    help.Add "Each running balance verified. Opening balance is derived from the first balance and movement; confirm it against the source statement summary."
    help.Add "Source rows retained in Source-row-audit.csv. Summary/page headings excluded. No descriptions/references invented."
    help.Add "Import monthly files OR Bank-Combined.csv, never both. Monthly files are recommended. Do not reimport statements already loaded."
    help.Add "Bank reconciliation > select correct bank ledger/scope > Import statement. Date format ISO; row order Oldest first; header row 1; mappings Auto."
    help.Add "Use Import-balances.csv for exact dates and balances; monthly periods reflect the first/last transaction dates, not an assumed full-month coverage."
    help.Add "Import is not a journal posting or transaction classification. Review matches and missing details before posting/closing."
    If reversed Then help.Add "Source transaction order reversed only after verifying chronological order and every running balance."
    For i = 1 To notes.Count: help.Add notes(i): Next i
    WriteLines folder & "\READ-ME.txt", help
    Set help = New Collection: help.Add "source_excel_row,date,debit,credit,balance"
    For i = 1 To data.Count
        rec = data(i): help.Add rec(7) & "," & rec(0) & "," & Money(CCur(rec(4))) & "," & Money(CCur(rec(5))) & "," & Money(CCur(rec(6)))
    Next i
    WriteLines folder & "\Source-row-audit.csv", help
    MsgBox "Converted and balance-checked " & data.Count & " transactions." & vbCrLf & "Monthly files: " & groups.Count & vbCrLf & "Missing narrations: " & missingNarration & "; references: " & missingReference & vbCrLf & "Saved in: " & folder & vbCrLf & "Import monthly OR combined, never both.", vbInformation
    GoTo CleanUp
Failed:
    MsgBox "Conversion stopped: " & Err.Description & vbCrLf & "The original statement was not saved or changed. If an output folder was created, treat it as incomplete and do not import it.", vbExclamation
CleanUp:
    On Error Resume Next
    If Not wb Is Nothing Then wb.Close SaveChanges:=False
    Application.AutomationSecurity = oldSecurity
    Application.EnableEvents = oldEvents: Application.ScreenUpdating = oldScreen
End Sub

Private Function FindHeader(ByVal ws As Worksheet, ByRef header As Long, ByRef cols() As Long) As Boolean
    Dim i As Long, j As Long, n As Long, k As Long, text As String
    For i = 1 To 100
        For k = 1 To 7: cols(k) = 0: Next k
        For j = 1 To WorksheetFunction.Min(100, ws.UsedRange.Column + ws.UsedRange.Columns.Count - 1)
            text = Normal(CStr(ws.Cells(i, j).Value2)): n = 0
            Select Case text
                Case "date", "transactiondate", "txndate": n = 1
                Case "valuedt", "valuedate": n = 2
                Case "narration", "description", "particulars": n = 3
                Case "chqrefno", "reference", "referenceno", "chequerefno": n = 4
                Case "withdrawalamt", "withdrawalamount", "debit", "debitamount": n = 5
                Case "depositamt", "depositamount", "credit", "creditamount": n = 6
                Case "closingbalance", "runningbalance", "balance": n = 7
            End Select
            If n > 0 Then
                If cols(n) <> 0 Then Err.Raise vbObjectError + 110, , "Ambiguous duplicate headings on row " & i
                cols(n) = j
            End If
        Next j
        If cols(1) * cols(5) * cols(6) * cols(7) <> 0 Then header = i: FindHeader = True: Exit Function
    Next i
End Function

Private Function Normal(ByVal text As String) As String
    Dim i As Long, c As String
    text = LCase$(text)
    For i = 1 To Len(text)
        c = Mid$(text, i, 1)
        If c Like "[a-z0-9]" Then Normal = Normal & c
    Next i
End Function

Private Function ReadDate(ByVal cell As Range, ByRef result As Date) As Boolean
    Dim text As String, parts As Variant, y As Long, m As Long, d As Long, value As Date
    On Error GoTo InvalidDate
    If IsError(cell.Value) Then Exit Function
    If VarType(cell.Value) = vbDate Then result = DateValue(cell.Value): ReadDate = True: Exit Function
    text = Trim$(CStr(cell.Value2)): text = Replace(text, "-", "/"): parts = Split(text, "/")
    If UBound(parts) <> 2 Then Exit Function
    If Not IsNumeric(parts(0)) Or Not IsNumeric(parts(1)) Or Not IsNumeric(parts(2)) Then Exit Function
    If Len(parts(0)) = 4 Then
        y = CLng(parts(0)): m = CLng(parts(1)): d = CLng(parts(2))
    Else
        d = CLng(parts(0)): m = CLng(parts(1)): y = CLng(parts(2))
        If Len(parts(2)) = 2 Then y = 2000 + y
    End If
    If y < 1900 Or y > 2099 Then Exit Function
    value = DateSerial(y, m, d)
    If Year(value) <> y Or Month(value) <> m Or Day(value) <> d Then Exit Function
    result = value: ReadDate = True
InvalidDate:
End Function

Private Function ReadMoney(ByVal cell As Range, ByVal blankOK As Boolean) As Currency
    Dim text As String, value As Variant, negative As Boolean
    If IsError(cell.Value2) Then Err.Raise vbObjectError + 111, , "Invalid amount at " & cell.Address
    text = Trim$(Replace(CStr(cell.Value2), ChrW(160), " "))
    If text = "" Then
        If blankOK Then Exit Function
        Err.Raise vbObjectError + 112, , "Missing balance at " & cell.Address
    End If
    If IsNumeric(cell.Value2) And VarType(cell.Value2) <> vbString Then
        value = CDec(cell.Value2)
    Else
        text = Replace(text, ",", ""): text = Replace(text, " ", "")
        If Left$(text, 1) = "(" And Right$(text, 1) = ")" Then text = "-" & Mid$(text, 2, Len(text) - 2)
        Dim re As Object: Set re = CreateObject("VBScript.RegExp")
        re.Pattern = "^[+-]?[0-9]+(\.[0-9]{1,2})?$"
        If Not re.Test(text) Then Err.Raise vbObjectError + 113, , "Invalid amount at " & cell.Address & ": " & text
        value = CDec(Replace(text, ".", Application.International(xlDecimalSeparator)))
    End If
    If Abs(value * 100 - Round(value * 100, 0)) > CDec(0.000001) Then Err.Raise vbObjectError + 114, , "More than two decimal places at " & cell.Address
    ReadMoney = CCur(value)
End Function

Private Function HasAmount(ByVal cell As Range) As Boolean
    Dim text As String
    If IsError(cell.Value2) Then HasAmount = True: Exit Function
    text = Trim$(CStr(cell.Value2))
    HasAmount = IsNumeric(Replace(text, ",", "")) And Len(text) > 0
End Function

Private Function CellText(ByVal ws As Worksheet, ByVal row As Long, ByVal col As Long) As String
    If col = 0 Then Exit Function
    If IsError(ws.Cells(row, col).Value2) Then Err.Raise vbObjectError + 115, , "Invalid text field at source row " & row
    CellText = Trim$(CStr(ws.Cells(row, col).Value2))
End Function

Private Function CheckRows(ByVal rows As Collection, ByRef opening As Currency, ByRef closing As Currency, ByRef reason As String) As Boolean
    Dim i As Long, rec As Variant, previousDate As String, running As Currency
    rec = rows(1): opening = CCur(rec(6)) + CCur(rec(4)) - CCur(rec(5)): running = opening
    For i = 1 To rows.Count
        rec = rows(i)
        If CStr(rec(0)) < previousDate Then reason = "Non-chronological date at source row " & rec(7): Exit Function
        running = running - CCur(rec(4)) + CCur(rec(5))
        If running <> CCur(rec(6)) Then reason = "Running balance mismatch at source row " & rec(7) & "; expected " & Money(running) & ", found " & Money(CCur(rec(6))): Exit Function
        previousDate = CStr(rec(0))
    Next i
    closing = running: CheckRows = True
End Function

Private Function Money(ByVal value As Currency) As String
    Money = Replace(Format$(value, "0.00"), Application.International(xlDecimalSeparator), ".")
End Function

Private Function Csv(ByVal text As String) As String
    'Guard spreadsheet formula interpretation without changing stored bank amounts.
    If Len(text) > 0 Then
        If InStr("=+-@", Left$(text, 1)) > 0 Then text = "'" & text
    End If
    Csv = """" & Replace(text, """", """""") & """"
End Function

Private Sub WriteTransactions(ByVal path As String, ByVal rows As Collection)
    Dim lines As Collection, i As Long, rec As Variant
    Set lines = New Collection: lines.Add "date,value_date,narration,reference,debit,credit,balance"
    For i = 1 To rows.Count
        rec = rows(i)
        lines.Add rec(0) & "," & rec(1) & "," & Csv(CStr(rec(2))) & "," & Csv(CStr(rec(3))) & "," & Money(CCur(rec(4))) & "," & Money(CCur(rec(5))) & "," & Money(CCur(rec(6)))
    Next i
    WriteLines path, lines
End Sub

Private Function SummaryLine(ByVal filename As String, ByVal rows As Collection) As String
    Dim first As Variant, last As Variant, opening As Currency
    first = rows(1): last = rows(rows.Count): opening = CCur(first(6)) + CCur(first(4)) - CCur(first(5))
    SummaryLine = filename & "," & first(0) & "," & last(0) & "," & rows.Count & "," & Money(opening) & "," & Money(CCur(last(6)))
End Function

Private Sub WriteLines(ByVal path As String, ByVal lines As Collection)
    Dim stream As Object, i As Long
    Set stream = CreateObject("ADODB.Stream"): stream.Type = 2: stream.Charset = "utf-8": stream.Open
    For i = 1 To lines.Count: stream.WriteText CStr(lines(i)) & vbCrLf: Next i
    stream.SaveToFile path, 1: stream.Close 'Never overwrite an existing file.
End Sub


Public Sub InstallConverterButton()
    Dim ws As Worksheet, button As Shape
    Set ws = ThisWorkbook.Worksheets(1)
    On Error Resume Next
    ws.Shapes("RunBankConverter").Delete
    On Error GoTo 0
    Set button = ws.Shapes.AddShape(5, 30, 500, 300, 45)
    button.Name = "RunBankConverter"
    button.TextFrame.Characters.Text = "Convert original bank statement"
    button.Fill.ForeColor.RGB = RGB(21, 76, 138)
    button.TextFrame.Characters.Font.Color = RGB(255, 255, 255)
    button.OnAction = "'" & Replace(ThisWorkbook.Name, "'", "''") & "'!ConvertBankStatement"
    MsgBox "Button added. Save this workbook as an Excel Macro-Enabled Workbook (.xlsm), close and reopen it, then run InstallConverterButton once more if you changed its name.", vbInformation
End Sub
