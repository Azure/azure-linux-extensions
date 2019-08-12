package exporterwrapper

import (
	"encoding/json"
	"fmt"
	"os"
	"time"

	"go.opencensus.io/trace"
)

/* This context information should be filled out by the 1Agent in the full implementation */
var AzureMonitorContext = map[string]interface{}{
	"ai.cloud.role":          "Go Application",
	"ai.cloud.roleInstance":  getHostName(),
	"ai.device.id":           getHostName(),
	"ai.device.type":         "Other",
	"ai.internal.sdkVersion": "go:exp0.1",
}

func getHostName() string {
	hostName, err := os.Hostname()
	if err != nil {
		fmt.Println("Problem with getting host name")
	}
	return hostName
}

func ConvertOCSpanDataToApplicationInsightsSchema(sd *trace.SpanData) string {
	envelope := Envelope{
		IKey: os.Getenv("APPLICATIONINSIGHTS_KEY"),
		Tags: AzureMonitorContext,
		Time: FormatTime(sd.StartTime),
	}

	envelope.Tags["ai.operation.id"] = sd.SpanContext.TraceID.String()
	if sd.ParentSpanID.String() != "0000000000000000" {
		envelope.Tags["ai.operation.parentId"] = "|" + sd.SpanContext.TraceID.String() + "." + sd.ParentSpanID.String() + "."
	}
	if sd.SpanKind == trace.SpanKindServer {
		envelope.Name = "Microsoft.ApplicationInsights.Request"
		currentData := Request{
			Id:           "|" + sd.SpanContext.TraceID.String() + "." + sd.SpanID.String() + ".",
			Duration:     TimeStampToDuration(sd.EndTime.Sub(sd.StartTime)),
			ResponseCode: "0",
			Success:      true,
		}
		if _, isIncluded := sd.Attributes["http.method"]; isIncluded {
			currentData.Name = fmt.Sprintf("%s", sd.Attributes["http.method"])
		}
		if _, isIncluded := sd.Attributes["http.url"]; isIncluded {
			currentData.Name = fmt.Sprintf("%s %s", currentData.Name, sd.Attributes["http.url"])
			currentData.Url = fmt.Sprintf("%s", sd.Attributes["http.url"])
		}
		if _, isIncluded := sd.Attributes["http.status_code"]; isIncluded {
			currentData.ResponseCode = fmt.Sprintf("%d", sd.Attributes["http.status_code"])
		}
		envelope.DataToSend = Data{
			BaseData: currentData,
			BaseType: "RequestData",
		}

	} else {
		envelope.Name = "Microsoft.ApplicationInsights.RemoteDependency"
		currentData := RemoteDependency{
			Name:       sd.Name,
			Id:         "|" + sd.SpanContext.TraceID.String() + "." + sd.SpanID.String() + ".",
			ResultCode: "0", // TODO: Out of scope for now
			Duration:   TimeStampToDuration(sd.EndTime.Sub(sd.StartTime)),
			Success:    true,
			Ver:        2,
		}
		if sd.SpanKind == trace.SpanKindClient {
			currentData.Type = "HTTP"
			if _, isIncluded := sd.Attributes["http.url"]; isIncluded {
				Url := fmt.Sprintf("%s", sd.Attributes["http.url"])
				currentData.Name = Url // TODO: parse URL before assignment
			}
			if _, isIncluded := sd.Attributes["http.status_code"]; isIncluded {
				currentData.ResultCode = fmt.Sprintf("%d", sd.Attributes["http.status_code"])
			}
		} else {
			currentData.Type = "INPROC"
		}
		envelope.DataToSend = Data{
			BaseData: currentData,
			BaseType: "RemoteDependencyData",
		}
	}

	bytesRepresentation, err := json.Marshal(envelope)
	if err != nil {
		fmt.Println(err)
	}

	return string(bytesRepresentation)
}

const (
	// All custom time formats for go have to be for the timestamp Jan 2 15:04:05 2006 MST
	// as mentioned here (https://godoc.org/time#Time.Format)
	TimeFormat = "2006-01-02T15:04:05.000000Z"
	HourOffset = 7 // TODO: Calculate time offset in a better way
)

/* Calculates number of days, hours, minutes, seconds, and milliseconds in a
time duration. Then it properly formats into a string.
@param t Time Duration
@return formatted string
*/
func TimeStampToDuration(t time.Duration) string {
	nanoSeconds := t.Nanoseconds()
	n := nanoSeconds / 1000000 //duration in milliseconds
	n, milliseconds := divMod(n, 1000)
	n, seconds := divMod(n, 60)
	n, minutes := divMod(n, 60)
	days, hours := divMod(n, 24)

	formattedDays := fmt.Sprintf("%01d", days)
	formattedHours := fmt.Sprintf("%02d", hours)
	formattedMinutes := fmt.Sprintf("%02d", minutes)
	formattedSeconds := fmt.Sprintf("%02d", seconds)
	formattedMilliseconds := fmt.Sprintf("%03d", milliseconds)

	return formattedDays + "." + formattedHours + ":" + formattedMinutes + ":" + formattedSeconds + "." + formattedMilliseconds
}

/* Performs division and returns both quotient and remainder. */
func divMod(numerator, denominator int64) (quotient, remainder int64) {
	quotient = numerator / denominator // integer division, decimals are truncated
	remainder = numerator % denominator
	return
}

/* Generates the current time stamp and properly formats to a string.
@return time stamp
*/
func FormatTime(t time.Time) string {
	t = t.Local().Add(time.Hour * HourOffset)
	formattedTime := t.Format(TimeFormat)
	return formattedTime
}

type Data struct {
	BaseData interface{} `json:"baseData"`
	BaseType string      `json:"baseType"`
}

type Envelope struct {
	IKey       string                 `json:"iKey"`
	Tags       map[string]interface{} `json:"tags"`
	Name       string                 `json:"name"`
	Time       string                 `json:"time"`
	DataToSend Data                   `json:"data"`
}

type RemoteDependency struct {
	Name       string `json:"name"`
	Id         string `json:"id"`
	ResultCode string `json:"resultCode"`
	Duration   string `json:"duration"`
	Success    bool   `json:"success"`
	Ver        int    `json:"ver"`
	Type       string `json:"type"`
}

type Request struct {
	Name         string `json:"name"`
	Id           string `json:"id"`
	Duration     string `json:"duration"`
	ResponseCode string `json:"responseCode"`
	Success      bool   `json:"success"`
	Url          string `json:"url"`
}
