# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Ground-truth content for the synthetic OCR samples: original exam-style Vietnamese text, formulas and tables.

Everything here is written for the benchmark, contains no personal data and may be published with the report.
"""

PARAGRAPHS = [
    "ĐỀ KIỂM TRA GIỮA HỌC KÌ I – MÔN TOÁN 10",
    "Thời gian làm bài: 90 phút, không kể thời gian phát đề.",
    "PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn. Thí sinh trả lời từ câu 1 đến câu 12. Mỗi câu hỏi thí sinh "
    "chỉ chọn một phương án.",
    "Câu 1. Cho tập hợp A gồm các số tự nhiên nhỏ hơn 6. Tập hợp A có bao nhiêu phần tử?",
    "A. 5.      B. 6.      C. 7.      D. 4.",
    "Câu 2. Mệnh đề phủ định của mệnh đề “Mọi học sinh trong lớp đều thích học môn Toán” là mệnh đề nào sau đây?",
    "Câu 3. Trong mặt phẳng tọa độ, cho hai điểm A(1; 2) và B(3; 6). Tọa độ trung điểm của đoạn thẳng AB là",
    "Câu 4. Một cửa hàng bán áo sơ mi với giá 250 nghìn đồng mỗi chiếc. Nếu khách mua từ ba chiếc trở lên thì được "
    "giảm 15% trên tổng số tiền. Hỏi khách mua bốn chiếc áo phải trả bao nhiêu tiền?",
    "PHẦN II. Câu trắc nghiệm đúng sai. Trong mỗi ý a), b), c), d) ở mỗi câu, thí sinh chọn đúng hoặc sai.",
    "Câu 5. Cho tam giác ABC có độ dài ba cạnh lần lượt là 5 cm, 12 cm và 13 cm. Xét tính đúng sai của các khẳng định "
    "sau: a) Tam giác ABC vuông tại đỉnh đối diện cạnh dài nhất; b) Diện tích tam giác bằng 30 cm²; c) Bán kính đường "
    "tròn ngoại tiếp bằng 6,5 cm; d) Chu vi tam giác bằng 31 cm.",
    "PHẦN III. Câu trắc nghiệm trả lời ngắn. Thí sinh trả lời từ câu 6 đến câu 8.",
    "Câu 6. Bác Hưng muốn rào một mảnh vườn hình chữ nhật có diện tích 200 mét vuông, một cạnh tựa vào bức tường có "
    "sẵn. Hỏi bác cần ít nhất bao nhiêu mét lưới để rào ba cạnh còn lại?",
    "Câu 7. Người ta thống kê số giờ tự học mỗi ngày của một nhóm học sinh và thu được mẫu số liệu: 2; 3; 3; 4; 5; 5; "
    "5; 6. Tìm số trung vị và mốt của mẫu số liệu trên.",
    "Câu 8. Nhiệt độ ngoài trời lúc 6 giờ sáng là 18 độ, đến trưa tăng thêm 9 độ rồi buổi tối giảm 4 độ. Hỏi nhiệt "
    "độ buổi tối là bao nhiêu?",
    "Ghi chú: Giám thị coi thi không giải thích gì thêm. Học sinh không được sử dụng tài liệu, được dùng máy tính cầm "
    "tay không có chức năng soạn thảo văn bản.",
    "Những nội dung trên nhằm kiểm tra khả năng nhận dạng chữ tiếng Việt có dấu: ắ ằ ẳ ẵ ặ, ấ ầ ẩ ẫ ậ, ế ề ể ễ ệ, "
    "ố ồ ổ ỗ ộ, ớ ờ ở ỡ ợ, ứ ừ ử ữ ự, ỳ ỷ ỹ ỵ, đường, nghiêng, khuỷu, quyết, giặt giũ.",
]

# LaTeX ground truth; every string renders with matplotlib mathtext (the generator's renderer).
FORMULAS = [
    r"x^2-5x+6=0",
    r"\frac{a+b}{2}\geq\sqrt{ab}",
    r"\sqrt{x^2+y^2}",
    r"\int_0^1 x^2\,dx=\frac{1}{3}",
    r"\sum_{k=1}^{n}k=\frac{n(n+1)}{2}",
    r"\lim_{x\to 0}\frac{\sin x}{x}=1",
    r"f(x)=\frac{2x-1}{x+3}",
    r"\Delta=b^2-4ac",
    r"x_{1,2}=\frac{-b\pm\sqrt{\Delta}}{2a}",
    r"\sin^2\alpha+\cos^2\alpha=1",
    r"\vec{u}=(1;-2;3)",
    r"y'=3x^2-6x",
    r"\log_2 8=3",
    r"a^m\cdot a^n=a^{m+n}",
    r"S=\pi r^2",
    r"\tan x=\frac{\sin x}{\cos x}",
    r"(a+b)^2=a^2+2ab+b^2",
    r"\int_1^e\frac{\ln x}{x}\,dx",
    r"\frac{1}{x-1}+\frac{2}{x+1}=1",
    r"P(A)=\frac{n(A)}{n(\Omega)}",
    r"u_n=u_1+(n-1)d",
    r"\left|x-2\right|<3",
    r"\cos 2x=1-2\sin^2x",
    r"e^{i\pi}+1=0",
    r"\sqrt[3]{27}=3",
    r"C_n^k=\frac{n!}{k!(n-k)!}",
    r"\overline{AB}",
    r"V=\frac{1}{3}Bh",
    r"\lim_{n\to\infty}\left(1+\frac{1}{n}\right)^n=e",
    r"2^{x+1}>16",
]

# Tables: first row is the header. Cell text uses Vietnamese with diacritics and numbers.
TABLES = [
    [["STT", "Họ và tên", "Điểm"], ["1", "Nguyễn Văn An", "8,5"], ["2", "Trần Thị Bích", "9,0"],
     ["3", "Lê Hoàng Dũng", "7,25"]],
    [["Mức độ", "Nhận biết", "Thông hiểu", "Vận dụng"], ["Số câu", "12", "8", "4"], ["Tỉ lệ", "40%", "30%", "30%"]],
    [["Giá trị x", "−2", "−1", "0", "1", "2"], ["f(x)", "7", "2", "−1", "−2", "−1"]],
    [["Tháng", "Doanh thu", "Chi phí", "Lợi nhuận"], ["Một", "120", "85", "35"], ["Hai", "135", "90", "45"],
     ["Ba", "150", "98", "52"], ["Tư", "142", "101", "41"]],
    [["Nội dung", "Yêu cầu cần đạt"], ["Mệnh đề", "Nhận biết mệnh đề, phủ định"],
     ["Tập hợp", "Thực hiện phép giao, hợp"],
     ["Bất phương trình", "Biểu diễn miền nghiệm"]],
    [["Lớp", "Sĩ số", "Giỏi", "Khá", "Trung bình"], ["10A1", "42", "15", "20", "7"], ["10A2", "40", "11", "22", "7"],
     ["10A3", "38", "9", "19", "10"]],
]
# The STT/name table uses invented sample names that belong to nobody; they exercise name-like diacritics.
