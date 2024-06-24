let table = base.getTable("Table 1");
let query = await table.selectRecordsAsync();

for (let record of query.records) {
    if (record.getCellValue("자막 생성 시작")) {
        let videoUrl = record.getCellValue("원본 동영상")[0].url;
        let country = record.getCellValue("나라 이름");
        let recordId = record.id;

        // Send data to the FastAPI server for subtitle generation
        let response = await fetch("https://your-app-name.herokuapp.com/automate/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                action: "create_subtitles",
                record_id: recordId,
                video_url: videoUrl,
                lang: country
            })
        });

        let result = await response.json();
        console.log(result);

        // Update Airtable record to show subtitle creation has started
        await table.updateRecordAsync(recordId, {
            "자막 생성 시작": false,
            "자막 생성중": true
        });
    }
}
