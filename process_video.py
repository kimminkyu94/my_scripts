let table = base.getTable("Table 1");
let query = await table.selectRecordsAsync();

for (let record of query.records) {
    if (record.getCellValue("동영상 생성 시작")) {
        let recordId = record.id;
        // Send data to the FastAPI server for video creation
        let response = await fetch("https://your-app-name.herokuapp.com/automate/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                action: "create_videos",
                record_id: recordId
            })
        });

        let result = await response.json();
        console.log(result);

        // Update Airtable record to show video creation has started
        await table.updateRecordAsync(recordId, {
            "동영상 생성 시작": false,
            "동영상 생성중": true
        });
    }
}
