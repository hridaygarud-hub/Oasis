
let user_id = localStorage.getItem("user_id");

if (!user_id) {
    user_id = Math.floor(Math.random() * 1000000);
    localStorage.setItem("user_id", user_id);
}

let startTime = Date.now();
let page = window.location.pathname;

window.onload = function () {

    fetch("/track", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            user_id: user_id,
            event_type: "visit",
            item_id: page,
            duration: ""
        })
    })

}

function track(item, url) {

    fetch("/track", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            user_id: user_id,
            event_type: "click",
            item_id: item,
            duration: ""
        })
    })
        .then(() => {
            if (url) {
                window.location.href = url
            }
        })

}

window.addEventListener("beforeunload", function () {

    let endTime = Date.now()
    let timeSpent = Math.floor((endTime - startTime) / 1000)

    let data = {
        user_id: user_id,
        event_type: "time_spent",
        item_id: page,
        duration: timeSpent
    }

    navigator.sendBeacon(
        "/track",
        new Blob([JSON.stringify(data)], { type: "application/json" })
    )

})