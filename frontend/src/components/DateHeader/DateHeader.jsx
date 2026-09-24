function DateHeader({ date }) {

    const d = new Date(date);

    const weekdays = [
        "일",
        "월",
        "화",
        "수",
        "목",
        "금",
        "토",
    ];

    const now = new Date();

    const year = d.getFullYear();
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const weekday = weekdays[d.getDay()];

    const time = d.toLocaleTimeString("ko-KR", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
    });

    const showYear = year !== now.getFullYear();

    return (
        <div className="date-header">
            <span>
                {showYear && `${year}년 `}
                {month}월 {day}일 ({weekday}) {time}
            </span>
        </div>
    );
}

export default DateHeader;