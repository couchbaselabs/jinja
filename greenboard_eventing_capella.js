function OnUpdate(doc,meta) {
    while (true) {
        try {
            if(doc === null || !(doc.hasOwnProperty('build') && doc.hasOwnProperty('build_id'))){
                return;
            }
            const build_version = doc['build'];
            const [doc_to_insert, doc_to_insert_meta] = get_build_document(build_version);
            const [all_jobs_document, all_jobs_document_meta] = get_all_jobs_document();
            let update_all_jobs_document = false;
            const os = doc['os'];
            const component = doc['component'];
            let name = doc['name'];
            const displayName = doc["displayName"] || name;
            let sub_component;
            if (typeof doc === undefined || doc.hasOwnProperty('subComponent')) {
                sub_component = doc['subComponent'];
            }
            else {
                sub_component = "";
            }
            if (!doc_to_insert.hasOwnProperty('os')) {
                doc_to_insert['os'] = {};
            }
            if (!doc_to_insert['os'].hasOwnProperty(os)) {
                doc_to_insert['os'][os] = {};
            }
            if (!doc_to_insert['os'][os].hasOwnProperty(component)){
                doc_to_insert['os'][os][component] = {}
            }
            if (!all_jobs_document.hasOwnProperty('capella')) {
                all_jobs_document['capella'] = {};
            }
            if (!all_jobs_document['capella'].hasOwnProperty(os)) {
                all_jobs_document['capella'][os] = {};
            }
            if (!all_jobs_document['capella'][os].hasOwnProperty(component)) {
                all_jobs_document['capella'][os][component] = {};
            }
            //const implementedIn = get_implemented_in(component, sub_component);
            const version = build_version.split('-')[0];
            if (!(displayName in all_jobs_document['capella'][os][component])) {
                all_jobs_document['capella'][os][component][displayName] = {
                    "totalCount" : doc['totalCount'],
                    "url" : doc['url'],
                    "priority" : doc['priority'],
                    "jobs_in" : [version]
                };
                update_all_jobs_document = true;
            }
            else {
                if (all_jobs_document['capella'][os][component][displayName]['jobs_in'].indexOf(version) == -1){
                    all_jobs_document['capella'][os][component][displayName]['jobs_in'].push(version);

                    all_jobs_document['capella'][os][component][displayName]['jobs_in'] =
                        all_jobs_document['capella'][os][component][displayName]['jobs_in'].sort().filter(function(item, pos, ary){
                        return !pos || item != ary[pos - 1];
                    })

                    update_all_jobs_document = true;

                }
            }
            var build_to_store = {
                "build_id": doc['build_id'],
                "claim": doc['claim'],
                "totalCount": doc['totalCount'],
                "result": doc['result'],
                "duration": doc['duration'],
                "url": doc['url'],
                "priority": doc['priority'],
                "failCount": doc['failCount'],
                "color": (doc.hasOwnProperty('color'))? doc['color']:'',
                "deleted": false,
                "olderBuild": false,
                "disabled": false,
                "displayName": displayName
            }
            if (doc.hasOwnProperty('provider')){
                build_to_store['provider'] = doc['provider']
            }
            if (doc.hasOwnProperty('env')) {
                build_to_store['env'] = doc['env']
            }
            if (doc.hasOwnProperty("skipCount")) {
                build_to_store["skipCount"] = doc["skipCount"]
            }
            if (doc["bugs"] !== undefined) {
                build_to_store["bugs"] = doc["bugs"]
            }
            if (doc["triage"] !== undefined) {
                build_to_store["triage"] = doc["triage"]
            }
            if (doc["servers"] !== undefined) {
                build_to_store["servers"] = doc["servers"]
            }
            if (doc["variants"] !== undefined) {
                build_to_store["variants"] = doc["variants"]
            }
            if (doc["timestamp"] !== undefined) {
                build_to_store["timestamp"] = doc["timestamp"]
            }
            let store_build = true;
            for (const [jobName, job] of Object.entries(doc_to_insert['os'][os][component])) {
                if (!store_build) {
                    break;
                }
                for (const run of job) {
                    if ((run["displayName"] || jobName) !== build_to_store["displayName"]) {
                        continue
                    }

                    // don't store the same build twice
                    if (run["build_id"] === build_to_store["build_id"]) {
                        store_build = false;
                        break;
                    }

                    const runVariants = run["variants"] || {}
                    const buildToStoreVariants = build_to_store["variants"] || {}

                    // all variants in run are the same in build_to_store
                    let existingVariantsSame = true;
                    for (const [variantName, variantValue] of Object.entries(runVariants)) {
                        if (buildToStoreVariants[variantName] !== variantValue) {
                            existingVariantsSame = false;
                            break;
                        }
                    }
                    if (!existingVariantsSame) {
                        continue
                    }

                    // same display name but different variants length so combine
                    name = jobName
                }
            }

            // name may have changed so create empty run list if job name doesn't exist
            if (!doc_to_insert['os'][os][component].hasOwnProperty(name)){
                doc_to_insert['os'][os][component][name] = []
            }

            if (!store_build){
                if(!update_all_jobs_document) {
                    return;
                }
            }
            else {
                doc_to_insert['os'][os][component][name].push(build_to_store);
                //Sort all the builds for the job and remove any duplicates from it.
                doc_to_insert['os'][os][component][name] = doc_to_insert['os'][os][component][name].sort(function(a, b){
                    return b['build_id'] - a['build_id'];
                }).filter(function(item, pos, ary){
                    return !pos || item.build_id != ary[pos - 1].build_id;
                });
                doc_to_insert['os'][os][component][name][0]['olderBuild'] = false;
                for(var i = 1; i < doc_to_insert['os'][os][component][name].length; i++ ){
                    doc_to_insert['os'][os][component][name][i]['olderBuild'] = true;
                }
                let counts = get_total_count(doc_to_insert);
                const totalCount = counts['totalCount'];
                const failCount = counts['failCount'];
                log('totalCount', totalCount);
                log('failCount', failCount);
                doc_to_insert['totalCount'] = totalCount;
                doc_to_insert['failCount'] = failCount;
                if (!replaceOrInsert(doc_to_insert_meta, doc_to_insert)) {
                    continue;
                }
            }
            if (update_all_jobs_document) {
                if (!replaceOrInsert(all_jobs_document_meta, all_jobs_document)) {
                    continue;
                }
            }
            break;
        } catch (e) {
            log("exception", e);
        }
    }

}
function OnDelete(meta) {
}

function replaceOrInsert(meta, doc) {
    if (meta.cas !== undefined) {
        const res = couchbase.replace(tgt, meta, doc);
        return res.success;
    } else {
        const res = couchbase.insert(tgt, meta, doc);
        return res.success;
    }
}

function get_build_document(build_version) {
    const doc_id = build_version.concat("_capella");
    const res = couchbase.get(tgt, { id: doc_id});
    if (res.success) {
        return [res.doc, res.meta];
    } else {
        const new_build_to_store = {
            "build": build_version,
            "totalCount": 0,
            "failCount": 0,
            "type": 'capella',
            "os": {}
        };
        return [new_build_to_store, { id: doc_id }];
    }
}

function get_all_jobs_document(){
    const res = couchbase.get(tgt, { id: "existing_builds_capella"});
    if (res.success) {
        return [res.doc, res.meta];
    } else {
        return [{}, { id: "existing_builds_capella" }];
    }
}



function get_total_count(doc_to_insert){
    let totalCount = 0;
    let failCount = 0;
    log('getting total count');
    try {
        let osKeys = Object.keys(doc_to_insert['os']);
        for (let os of osKeys){
            let componentKeys = Object.keys(doc_to_insert['os'][os]);
            for(let component of componentKeys){
                let jobNameKeys = Object.keys(doc_to_insert['os'][os][component]);
                for(let jobName of jobNameKeys){
                    if (doc_to_insert['os'][os][component][jobName].length > 0){
                        let olderBuild = doc_to_insert['os'][os][component][jobName][0];
                        totalCount += olderBuild['totalCount'];
                        failCount += olderBuild['failCount'];
                    }
                }
            }
        }
    } catch (e) {
        log('Exception in get_total_count', e);
    }
    return {"totalCount": totalCount, "failCount": failCount};
}