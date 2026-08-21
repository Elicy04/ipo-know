The Alibaba Cloud Model Studio knowledge base provides open APIs that enable you to integrate with your existing business systems, automate operations, and address complex retrieval needs.

**Important**

This document is for knowledge bases for document search only.

## **Prerequisites**

1.  To manage a knowledge base with APIs, [a RAM user](https://help.aliyun.com/en/model-studio/application-permission-management-overview#24ca2dad7djzs) must get [API permissions](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) (the AliyunBailianDataFullAccess policy) and [join a workspace](https://help.aliyun.com/en/model-studio/grant-the-business-space-permission-to-ram-users). This is not required for an Alibaba Cloud account.
    
    > A RAM user can manage knowledge bases only in workspaces they have joined. An Alibaba Cloud account can manage knowledge bases in all workspaces.
    
2.  Install the latest version of the [Alibaba Cloud Model Studio SDK](https://api.aliyun.com/api-tools/sdk/bailian?version=2023-12-29&language=python-tea&tab=primer-doc) to call the knowledge base APIs. For installation instructions, see the [Alibaba Cloud SDK Development Reference](https://help.aliyun.com/en/sdk/developer-reference/).
    
    > If the SDK does not meet your requirements, you can call the knowledge base APIs via HTTP requests using the [signature mechanism](https://help.aliyun.com/en/sdk/product-overview/v3-request-structure-and-signature). For connection details, see [API Overview](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-overview).
    
3.  [Get an AccessKey ID and an AccessKey Secret](https://help.aliyun.com/en/sdk/developer-reference/configure-the-alibaba-cloud-accesskey-environment-variable-on-linux-macos-and-windows-systems), and [a workspace ID](https://help.aliyun.com/en/model-studio/use-workspace#3d584de2733bp). Configure them as system environment variables to run the sample code. The following example shows how to set these variables in Linux:
    
    > If you use an IDE or other development plugins, configure the `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, and `WORKSPACE_ID` variables in your development environment.
    
    ```
    export ALIBABA_CLOUD_ACCESS_KEY_ID='Your AccessKey ID'
    export ALIBABA_CLOUD_ACCESS_KEY_SECRET='Your AccessKey Secret'
    export WORKSPACE_ID='Your Alibaba Cloud Model Studio workspace ID'
    ```
    
4.  Prepare the sample knowledge document [Alibaba Cloud Model Studio Phone Introduction.docx](https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/en-US/20251104/hzzpgq/Bailian+Phones+Specifications.docx) to create a knowledge base.
    

## **Sample code**

## Create a knowledge base

**Important**

-   Before calling this example, complete the [prerequisites](#a4a15bd543can) and ensure the RAM user has the [AliyunBailianDataFullAccess policy](https://help.aliyun.com/en/model-studio/grant-data-access-permission-to-ram-user).
    
-   If you use an IDE or other development plugins, set the `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, and `WORKSPACE_ID` environment variables in your development environment.
    

## Python

```
# This sample code is for reference only. Do not use it in a production environment.
import hashlib
import os
import time

import requests
from alibabacloud_bailian20231229 import models as bailian_20231229_models
from alibabacloud_bailian20231229.client import Client as bailian20231229Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models


def check_environment_variables():
    """Verifies that the required environment variables are set."""
    required_vars = {
        'ALIBABA_CLOUD_ACCESS_KEY_ID': 'Alibaba Cloud AccessKey ID',
        'ALIBABA_CLOUD_ACCESS_KEY_SECRET': 'Alibaba Cloud AccessKey Secret',
        'WORKSPACE_ID': 'Alibaba Cloud Model Studio workspace ID'
    }
    missing_vars = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing_vars.append(var)
            print(f"Error: Please set the {var} environment variable ({description}).")
    
    return len(missing_vars) == 0


def calculate_md5(file_path: str) -> str:
    """
    Calculates the MD5 hash of a file.

    Args:
        file_path (str): The local path of the file.

    Returns:
        str: The MD5 hash of the file.
    """
    md5_hash = hashlib.md5()

    # Read the file in binary mode.
    with open(file_path, "rb") as f:
        # Read the file in chunks to conserve memory when processing large files.
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)

    return md5_hash.hexdigest()


def get_file_size(file_path: str) -> int:
    """
    Returns the size of a file in bytes.
    Args:
        file_path (str): The local path of the file.
    Returns:
        int: The file size in bytes.
    """
    return os.path.getsize(file_path)


# Initialize the client.
def create_client() -> bailian20231229Client:
    """
    Creates and configures a client.

    Returns:
        bailian20231229Client: The configured client.
    """
    config = open_api_models.Config(
        access_key_id=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID'),
        access_key_secret=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    )
    # This endpoint is for the China (Beijing) region. Modify it if you use a different region.
    config.endpoint = 'bailian.cn-beijing.aliyuncs.com'
    return bailian20231229Client(config)


# Request a file upload lease.
def apply_lease(client, category_id, file_name, file_md5, file_size, workspace_id):
    """
    Requests a file upload lease from the Model Studio service.

    Args:
        client (bailian20231229Client): The client.
        category_id (str): The category ID.
        file_name (str): The file name.
        file_md5 (str): The MD5 hash of the file.
        file_size (int): The file size in bytes.
        workspace_id (str): The workspace ID.

    Returns:
        The response from the Model Studio service.
    """
    headers = {}
    request = bailian_20231229_models.ApplyFileUploadLeaseRequest(
        file_name=file_name,
        md_5=file_md5,
        size_in_bytes=file_size,
    )
    runtime = util_models.RuntimeOptions()
    return client.apply_file_upload_lease_with_options(category_id, workspace_id, request, headers, runtime)


# Upload the file to temporary storage.
def upload_file(pre_signed_url, headers, file_path):
    """
    Uploads the file to the presigned URL from the upload lease.
    Args:
        pre_signed_url (str): The URL from the upload lease.
        headers (dict): The request headers for the upload.
        file_path (str): The local path of the file.
    """
    with open(file_path, 'rb') as f:
        file_content = f.read()
    upload_headers = {
        "X-bailian-extra": headers["X-bailian-extra"],
        "Content-Type": headers["Content-Type"]
    }
    response = requests.put(pre_signed_url, data=file_content, headers=upload_headers)
    response.raise_for_status()


# Add the file to a category.
def add_file(client: bailian20231229Client, lease_id: str, parser: str, category_id: str, workspace_id: str):
    """
    Adds the file to a specified category in the Model Studio service.

    Args:
        client (bailian20231229Client): The client.
        lease_id (str): The lease ID.
        parser (str): The parser for the file.
        category_id (str): The category ID.
        workspace_id (str): The workspace ID.

    Returns:
        The response from the Model Studio service.
    """
    headers = {}
    request = bailian_20231229_models.AddFileRequest(
        lease_id=lease_id,
        parser=parser,
        category_id=category_id,
    )
    runtime = util_models.RuntimeOptions()
    return client.add_file_with_options(workspace_id, request, headers, runtime)


# Query the parsing status of the file.
def describe_file(client, workspace_id, file_id):
    """
    Gets the basic information about a file.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        file_id (str): The file ID.

    Returns:
        The response from the Model Studio service.
    """
    headers = {}
    runtime = util_models.RuntimeOptions()
    return client.describe_file_with_options(workspace_id, file_id, headers, runtime)


# Initialize the knowledge base (index).
def create_index(client, workspace_id, file_id, name, structure_type, source_type, sink_type):
    """
    Creates a knowledge base (initializes an index) in the Model Studio service.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        file_id (str): The file ID.
        name (str): The name of the knowledge base.
        structure_type (str): The data type of the knowledge base.
        source_type (str): The data source type. For example, the script uses 'DATA_CENTER_FILE'.
        sink_type (str): The vector storage type for the knowledge base.

    Returns:
        The response from the Model Studio service.
    """
    headers = {}
    request = bailian_20231229_models.CreateIndexRequest(
        structure_type=structure_type,
        name=name,
        source_type=source_type,
        sink_type=sink_type,
        document_ids=[file_id]
    )
    runtime = util_models.RuntimeOptions()
    return client.create_index_with_options(workspace_id, request, headers, runtime)


# Submit an indexing task.
def submit_index(client, workspace_id, index_id):
    """
    Submits an indexing task to the Model Studio service.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        index_id (str): The knowledge base ID.

    Returns:
        The response from the Model Studio service.
    """
    headers = {}
    submit_index_job_request = bailian_20231229_models.SubmitIndexJobRequest(
        index_id=index_id
    )
    runtime = util_models.RuntimeOptions()
    return client.submit_index_job_with_options(workspace_id, submit_index_job_request, headers, runtime)


# Get the status of an indexing task.
def get_index_job_status(client, workspace_id, job_id, index_id):
    """
    Queries the status of an indexing task.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        index_id (str): The knowledge base ID.
        job_id (str): The ID of the indexing task.

    Returns:
        The response from the Model Studio service.
    """
    headers = {}
    get_index_job_status_request = bailian_20231229_models.GetIndexJobStatusRequest(
        index_id=index_id,
        job_id=job_id
    )
    runtime = util_models.RuntimeOptions()
    return client.get_index_job_status_with_options(workspace_id, get_index_job_status_request, headers, runtime)


def create_knowledge_base(
        file_path: str,
        workspace_id: str,
        name: str
):
    """
    Creates a knowledge base in Model Studio.
    Args:
        file_path (str): The local path of the file.
        workspace_id (str): The workspace ID.
        name (str): The name of the knowledge base.
    Returns:
        str or None: The knowledge base ID on success, or None on failure.
    """
    # Set default values.
    category_id = 'default'
    parser = 'DASHSCOPE_DOCMIND'
    source_type = 'DATA_CENTER_FILE'
    structure_type = 'unstructured'
    sink_type = 'DEFAULT'
    try:
        # Step 1: Initialize the client.
        print("Step 1: Initializing the client...")
        client = create_client()
        # Step 2: Prepare file information.
        print("Step 2: Preparing file information...")
        file_name = os.path.basename(file_path)
        file_md5 = calculate_md5(file_path)
        file_size = get_file_size(file_path)
        # Step 3: Request an upload lease.
        print("Step 3: Requesting an upload lease from Model Studio...")
        lease_response = apply_lease(client, category_id, file_name, file_md5, file_size, workspace_id)
        lease_id = lease_response.body.data.file_upload_lease_id
        upload_url = lease_response.body.data.param.url
        upload_headers = lease_response.body.data.param.headers
        # Step 4: Upload the file.
        print("Step 4: Uploading the file to Model Studio...")
        upload_file(upload_url, upload_headers, file_path)
        # Step 5: Add the file to the server.
        print("Step 5: Adding the file to Model Studio...")
        add_response = add_file(client, lease_id, parser, category_id, workspace_id)
        file_id = add_response.body.data.file_id
        # Step 6: Check the file status.
        print("Step 6: Checking the file status in Model Studio...")
        while True:
            describe_response = describe_file(client, workspace_id, file_id)
            status = describe_response.body.data.status
            print(f"Current file status: {status}")
            if status == 'INIT':
                print("File is pending parsing. Please wait...")
            elif status == 'PARSING':
                print("File is parsing. Please wait...")
            elif status == 'PARSE_SUCCESS':
                print("File parsed successfully!")
                break
            else:
                print(f"Unknown file status: {status}. Please contact technical support.")
                return None
            time.sleep(5)
        # Step 7: Initialize the knowledge base.
        print("Step 7: Initializing the knowledge base in Model Studio...")
        index_response = create_index(client, workspace_id, file_id, name, structure_type, source_type, sink_type)
        index_id = index_response.body.data.id
        # Step 8: Submit an indexing task.
        print("Step 8: Submitting the indexing task to Model Studio...")
        submit_response = submit_index(client, workspace_id, index_id)
        job_id = submit_response.body.data.id
        # Step 9: Get the status of the indexing task.
        print("Step 9: Getting the indexing task status from Model Studio...")
        while True:
            get_index_job_status_response = get_index_job_status(client, workspace_id, job_id, index_id)
            status = get_index_job_status_response.body.data.status
            print(f"Current indexing task status: {status}")
            if status == 'COMPLETED':
                break
            time.sleep(5)
        print("Model Studio knowledge base created successfully!")
        return index_id
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def main():
    if not check_environment_variables():
        print("Environment variable check failed.")
        return
    file_path = input("Enter the local path of the file to upload (e.g., /path/to/file.docx): ")
    kb_name = input("Enter a name for your knowledge base: ")
    workspace_id = os.environ.get('WORKSPACE_ID')
    create_knowledge_base(file_path, workspace_id, kb_name)


if __name__ == '__main__':
    main()
```

## Java

```
// This sample code is for reference only. Do not use it in a production environment.
import com.aliyun.bailian20231229.models.*;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.File;
import java.io.FileInputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.TimeUnit;

public class KnowledgeBaseCreate {

    /**
     * Checks for required environment variables and prompts for any that are missing.
     *
     * @return true if all required environment variables are set, false otherwise.
     */
    public static boolean checkEnvironmentVariables() {
        Map<String, String> requiredVars = new HashMap<>();
        requiredVars.put("ALIBABA_CLOUD_ACCESS_KEY_ID", "Alibaba Cloud AccessKey ID");
        requiredVars.put("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "Alibaba Cloud AccessKey secret");
        requiredVars.put("WORKSPACE_ID", "Alibaba Cloud Model Studio workspace ID");

        List<String> missingVars = new ArrayList<>();
        for (Map.Entry<String, String> entry : requiredVars.entrySet()) {
            String value = System.getenv(entry.getKey());
            if (value == null || value.isEmpty()) {
                missingVars.add(entry.getKey());
                System.out.println("Error: Set the " + entry.getKey() + " environment variable (" + entry.getValue() + ")");
            }
        }

        return missingVars.isEmpty();
    }

    /**
     * Calculates the MD5 hash of a file.
     *
     * @param filePath The local path of the file.
     * @return The MD5 hash of the file.
     * @throws Exception if an error occurs.
     */
    public static String calculateMD5(String filePath) throws Exception {
        MessageDigest md = MessageDigest.getInstance("MD5");
        try (FileInputStream fis = new FileInputStream(filePath)) {
            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = fis.read(buffer)) != -1) {
                md.update(buffer, 0, bytesRead);
            }
        }
        StringBuilder sb = new StringBuilder();
        for (byte b : md.digest()) {
            sb.append(String.format("%02x", b & 0xff));
        }
        return sb.toString();
    }

    /**
     * Gets the file size in bytes.
     *
     * @param filePath The local path of the file.
     * @return The file size in bytes.
     */
    public static String getFileSize(String filePath) {
        File file = new File(filePath);
        long fileSize = file.length();
        return String.valueOf(fileSize);
    }

    /**
     * Initializes the client.
     *
     * @return The configured client object.
     */
    public static com.aliyun.bailian20231229.Client createClient() throws Exception {
        com.aliyun.teaopenapi.models.Config config = new com.aliyun.teaopenapi.models.Config()
                .setAccessKeyId(System.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"))
                .setAccessKeySecret(System.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"));
        // The following endpoint is a public cloud endpoint. You can change the endpoint as needed.
        config.endpoint = "bailian.cn-beijing.aliyuncs.com";
        return new com.aliyun.bailian20231229.Client(config);
    }

    /**
     * Requests a file upload lease.
     *
     * @param client      The client object.
     * @param categoryId  The category ID.
     * @param fileName    The file name.
     * @param fileMd5     The MD5 hash of the file.
     * @param fileSize    The file size in bytes.
     * @param workspaceId The workspace ID.
     * @return The response from Alibaba Cloud Model Studio.
     */
    public static ApplyFileUploadLeaseResponse applyLease(com.aliyun.bailian20231229.Client client, String categoryId, String fileName, String fileMd5, String fileSize, String workspaceId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.ApplyFileUploadLeaseRequest applyFileUploadLeaseRequest = new com.aliyun.bailian20231229.models.ApplyFileUploadLeaseRequest();
        applyFileUploadLeaseRequest.setFileName(fileName);
        applyFileUploadLeaseRequest.setMd5(fileMd5);
        applyFileUploadLeaseRequest.setSizeInBytes(fileSize);
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        ApplyFileUploadLeaseResponse applyFileUploadLeaseResponse = null;
        applyFileUploadLeaseResponse = client.applyFileUploadLeaseWithOptions(categoryId, workspaceId, applyFileUploadLeaseRequest, headers, runtime);
        return applyFileUploadLeaseResponse;
    }

    /**
     * Uploads the file to temporary storage.
     *
     * @param preSignedUrl The URL from the upload lease.
     * @param headers      The request headers for the upload.
     * @param filePath     The local path of the file.
     * @throws Exception if an error occurs.
     */
    public static void uploadFile(String preSignedUrl, Map<String, String> headers, String filePath) throws Exception {
        File file = new File(filePath);
        if (!file.exists() || !file.isFile()) {
            throw new IllegalArgumentException("The file does not exist or is not a regular file: " + filePath);
        }

        try (FileInputStream fis = new FileInputStream(file)) {
            URL url = new URL(preSignedUrl);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("PUT");
            conn.setDoOutput(true);

            // Set the upload request headers.
            conn.setRequestProperty("X-bailian-extra", headers.get("X-bailian-extra"));
            conn.setRequestProperty("Content-Type", headers.get("Content-Type"));

            // Read and upload the file in chunks.
            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = fis.read(buffer)) != -1) {
                conn.getOutputStream().write(buffer, 0, bytesRead);
            }

            int responseCode = conn.getResponseCode();
            if (responseCode != 200) {
                throw new RuntimeException("Upload failed: " + responseCode);
            }
        }
    }

    /**
     * Adds the file to a category.
     *
     * @param client      The client object.
     * @param leaseId     The lease ID.
     * @param parser      The file parser.
     * @param categoryId  The category ID.
     * @param workspaceId The workspace ID.
     * @return The response from the Alibaba Cloud Model Studio service.
     */
    public static AddFileResponse addFile(com.aliyun.bailian20231229.Client client, String leaseId, String parser, String categoryId, String workspaceId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.AddFileRequest addFileRequest = new com.aliyun.bailian20231229.models.AddFileRequest();
        addFileRequest.setLeaseId(leaseId);
        addFileRequest.setParser(parser);
        addFileRequest.setCategoryId(categoryId);
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        return client.addFileWithOptions(workspaceId, addFileRequest, headers, runtime);
    }

    /**
     * Gets information about a file.
     *
     * @param client      The client object.
     * @param workspaceId The workspace ID.
     * @param fileId      The file ID.
     * @return The response from the Alibaba Cloud Model Studio service.
     */
    public static DescribeFileResponse describeFile(com.aliyun.bailian20231229.Client client, String workspaceId, String fileId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        return client.describeFileWithOptions(workspaceId, fileId, headers, runtime);
    }

    /**
     * Creates a knowledge base (initializes an index) in Alibaba Cloud Model Studio.
     *
     * @param client        The client object.
     * @param workspaceId   The workspace ID.
     * @param fileId        The file ID.
     * @param name          The knowledge base name.
     * @param structureType The data structure of the knowledge base.
     * @param sourceType    The data source type. Supported types are category and file.
     * @param sinkType      The vector storage type for the knowledge base.
     * @return The response from the Alibaba Cloud Model Studio service.
     */
    public static CreateIndexResponse createIndex(com.aliyun.bailian20231229.Client client, String workspaceId, String fileId, String name, String structureType, String sourceType, String sinkType) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.CreateIndexRequest createIndexRequest = new com.aliyun.bailian20231229.models.CreateIndexRequest();
        createIndexRequest.setStructureType(structureType);
        createIndexRequest.setName(name);
        createIndexRequest.setSourceType(sourceType);
        createIndexRequest.setSinkType(sinkType);
        createIndexRequest.setDocumentIds(Collections.singletonList(fileId));
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        return client.createIndexWithOptions(workspaceId, createIndexRequest, headers, runtime);
    }

    /**
     * Submits an indexing task to Alibaba Cloud Model Studio.
     *
     * @param client      The client object.
     * @param workspaceId The workspace ID.
     * @param indexId     The knowledge base ID.
     * @return The response from the Alibaba Cloud Model Studio service.
     */
    public static SubmitIndexJobResponse submitIndex(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.SubmitIndexJobRequest submitIndexJobRequest = new com.aliyun.bailian20231229.models.SubmitIndexJobRequest();
        submitIndexJobRequest.setIndexId(indexId);
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        return client.submitIndexJobWithOptions(workspaceId, submitIndexJobRequest, headers, runtime);
    }

    /**
     * Gets the status of an indexing task.
     *
     * @param client      The client object.
     * @param workspaceId The workspace ID.
     * @param jobId       The task ID.
     * @param indexId     The knowledge base ID.
     * @return The response from the Alibaba Cloud Model Studio service.
     */
    public static GetIndexJobStatusResponse getIndexJobStatus(com.aliyun.bailian20231229.Client client, String workspaceId, String jobId, String indexId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.GetIndexJobStatusRequest getIndexJobStatusRequest = new com.aliyun.bailian20231229.models.GetIndexJobStatusRequest();
        getIndexJobStatusRequest.setIndexId(indexId);
        getIndexJobStatusRequest.setJobId(jobId);
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        GetIndexJobStatusResponse getIndexJobStatusResponse = null;
        getIndexJobStatusResponse = client.getIndexJobStatusWithOptions(workspaceId, getIndexJobStatusRequest, headers, runtime);
        return getIndexJobStatusResponse;
    }

    /**
     * Creates a knowledge base in Alibaba Cloud Model Studio.
     *
     * @param filePath    The local path of the file.
     * @param workspaceId The workspace ID.
     * @param name        The knowledge base name.
     * @return The knowledge base ID if successful; otherwise, null.
     */
    public static String createKnowledgeBase(String filePath, String workspaceId, String name) {
        // Set default values.
        String categoryId = "default";
        String parser = "DASHSCOPE_DOCMIND";
        String sourceType = "DATA_CENTER_FILE";
        String structureType = "unstructured";
        String sinkType = "DEFAULT";
        try {
            // Step 1: Initializing the client.
            System.out.println("Step 1: Initializing the client.");
            com.aliyun.bailian20231229.Client client = createClient();

            // Step 2: Preparing file information.
            System.out.println("Step 2: Preparing file information.");
            String fileName = new File(filePath).getName();
            String fileMd5 = calculateMD5(filePath);
            String fileSize = getFileSize(filePath);

            // Step 3: Requesting an upload lease from Alibaba Cloud Model Studio.
            System.out.println("Step 3: Requesting an upload lease from Alibaba Cloud Model Studio.");
            ApplyFileUploadLeaseResponse leaseResponse = applyLease(client, categoryId, fileName, fileMd5, fileSize, workspaceId);
            String leaseId = leaseResponse.getBody().getData().getFileUploadLeaseId();
            String uploadUrl = leaseResponse.getBody().getData().getParam().getUrl();
            Object uploadHeaders = leaseResponse.getBody().getData().getParam().getHeaders();

            // Step 4: Uploading the file to Alibaba Cloud Model Studio.
            System.out.println("Step 4: Uploading the file to Alibaba Cloud Model Studio.");
            // The jackson-databind dependency is required.
            // Convert the uploadHeaders from the previous step to a Map (key-value pairs).
            ObjectMapper mapper = new ObjectMapper();
            Map<String, String> uploadHeadersMap = (Map<String, String>) mapper.readValue(mapper.writeValueAsString(uploadHeaders), Map.class);
            uploadFile(uploadUrl, uploadHeadersMap, filePath);

            // Step 5: Adding the file to the Alibaba Cloud Model Studio server.
            System.out.println("Step 5: Adding the file to the Alibaba Cloud Model Studio server.");
            AddFileResponse addResponse = addFile(client, leaseId, parser, categoryId, workspaceId);
            String fileId = addResponse.getBody().getData().getFileId();

            // Step 6: Checking the file status in Alibaba Cloud Model Studio.
            System.out.println("Step 6: Checking the file status in Alibaba Cloud Model Studio.");
            while (true) {
                DescribeFileResponse describeResponse = describeFile(client, workspaceId, fileId);
                String status = describeResponse.getBody().getData().getStatus();
                System.out.println("Current file status: " + status);

                if (status.equals("INIT")) {
                    System.out.println("The file is pending parsing.");
                } else if (status.equals("PARSING")) {
                    System.out.println("The file is being parsed.");
                } else if (status.equals("PARSE_SUCCESS")) {
                    System.out.println("File parsed successfully.");
                    break;
                } else {
                    System.out.println("Unknown file status: " + status + ". Contact technical support.");
                    return null;
                }
                TimeUnit.SECONDS.sleep(5);
            }

            // Step 7: Creating the knowledge base in Alibaba Cloud Model Studio.
            System.out.println("Step 7: Creating the knowledge base in Alibaba Cloud Model Studio.");
            CreateIndexResponse indexResponse = createIndex(client, workspaceId, fileId, name, structureType, sourceType, sinkType);
            String indexId = indexResponse.getBody().getData().getId();

            // Step 8: Submitting an indexing task to Alibaba Cloud Model Studio.
            System.out.println("Step 8: Submitting an indexing task to Alibaba Cloud Model Studio.");
            SubmitIndexJobResponse submitResponse = submitIndex(client, workspaceId, indexId);
            String jobId = submitResponse.getBody().getData().getId();

            // Step 9: Getting the status of the indexing task from Alibaba Cloud Model Studio.
            System.out.println("Step 9: Getting the status of the indexing task from Alibaba Cloud Model Studio.");
            while (true) {
                GetIndexJobStatusResponse getStatusResponse = getIndexJobStatus(client, workspaceId, jobId, indexId);
                String status = getStatusResponse.getBody().getData().getStatus();
                System.out.println("Current indexing task status: " + status);

                if (status.equals("COMPLETED")) {
                    break;
                }
                TimeUnit.SECONDS.sleep(5);
            }

            System.out.println("The knowledge base was created successfully.");
            return indexId;

        } catch (Exception e) {
            System.out.println("An error occurred: " + e.getMessage());
            e.printStackTrace();
            return null;
        }
    }

    /**
     * The main entry point for the application.
     */
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        if (!checkEnvironmentVariables()) {
            return;
        }

        System.out.print("Enter the local path to the file to upload. For example, on Linux: /xxx/xxx/Alibaba_Cloud_Model_Studio_Phone_Series_Introduction.docx:");
        String filePath = scanner.nextLine();

        System.out.print("Enter a name for your knowledge base: ");
        String kbName = scanner.nextLine();

        String workspaceId = System.getenv("WORKSPACE_ID");
        String result = createKnowledgeBase(filePath, workspaceId, kbName);
        if (result != null) {
            System.out.println("Knowledge base ID: " + result);
        }
    }
}
```

## PHP

```
<?php
// This sample code is for reference only. Do not use it in a production environment.
namespace AlibabaCloud\SDK\Sample;

use AlibabaCloud\Dara\Models\RuntimeOptions;
use AlibabaCloud\SDK\Bailian\V20231229\Bailian;
use AlibabaCloud\SDK\Bailian\V20231229\Models\AddFileRequest;
use \Exception;

use Darabonba\OpenApi\Models\Config;
use AlibabaCloud\SDK\Bailian\V20231229\Models\ApplyFileUploadLeaseRequest;
use AlibabaCloud\SDK\Bailian\V20231229\Models\CreateIndexRequest;
use AlibabaCloud\SDK\Bailian\V20231229\Models\SubmitIndexJobRequest;
use AlibabaCloud\SDK\Bailian\V20231229\Models\GetIndexJobStatusRequest;

class KnowledgeBaseCreate {

    /**
    * Checks for and prompts you to set the required environment variables.
    *
    * @return bool true if all required environment variables are set; otherwise, false.
    */
    public static function checkEnvironmentVariables() {
        $requiredVars = [
            'ALIBABA_CLOUD_ACCESS_KEY_ID' => 'Alibaba Cloud AccessKey ID',
            'ALIBABA_CLOUD_ACCESS_KEY_SECRET' => 'Alibaba Cloud AccessKey secret',
            'WORKSPACE_ID' => 'Alibaba Cloud Model Studio workspace ID'
        ];
        $missingVars = [];
        foreach ($requiredVars as $var => $description) {
            if (!getenv($var)) {
                $missingVars[] = $var;
                echo "Error: Set the $var environment variable ($description)\n";
            }
        }
        return count($missingVars) === 0;
    }

    /**
     * Calculates the MD5 hash of a file.
     *
     * @param string $filePath The local path of the file.
     * @return string The MD5 hash of the file.
     */
    public static function calculateMd5($filePath) {
        $md5Hash = hash_init("md5");
        $handle = fopen($filePath, "rb");
        while (!feof($handle)) {
            $chunk = fread($handle, 4096);
            hash_update($md5Hash, $chunk);
        }
        fclose($handle);
        return hash_final($md5Hash);
    }

    /**
     * Gets the file size in bytes.
     *
     * @param string $filePath The local path of the file.
     * @return int The file size in bytes.
     */
    public static function getFileSize($filePath) {
        return (string)filesize($filePath);
    }

    /**
     * Initializes the client.
     *
     * @return Bailian The configured client object.
     */
    public static function createClient(){
        $config = new Config([
            "accessKeyId" => getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"), 
            "accessKeySecret" => getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        ]);
        // The following endpoint is for the public cloud. You can change it as needed.
        $config->endpoint = 'bailian.cn-beijing.aliyuncs.com';
        return new Bailian($config);
    }

    /**
     * Applies for a file upload lease.
     *
     * @param Bailian $client The client.
     * @param string $categoryId The category ID.
     * @param string $fileName The file name.
     * @param string $fileMd5 The MD5 hash of the file.
     * @param int $fileSize The file size in bytes.
     * @param string $workspaceId The workspace ID.
     * @return ApplyFileUploadLeaseResponse The service response.
     */
    public static function applyLease($client, $categoryId, $fileName, $fileMd5, $fileSize, $workspaceId) {
        $headers = [];
        $applyFileUploadLeaseRequest = new ApplyFileUploadLeaseRequest([
            "fileName" => $fileName,
            "md5" => $fileMd5,
            "sizeInBytes" => $fileSize
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->applyFileUploadLeaseWithOptions($categoryId, $workspaceId, $applyFileUploadLeaseRequest, $headers, $runtime);
    }

    /**
     * Uploads the file to temporary storage.
    *
    * @param string $preSignedUrl The URL from the upload lease.
    * @param array $headers The request headers for the upload.
    * @param string $filePath The local path of the file.
    */
    public static function uploadFile($preSignedUrl, $headers, $filePath) {
        $fileContent = file_get_contents($filePath);
        // Set the upload request headers.
        $uploadHeaders = [
            "X-bailian-extra" => $headers["X-bailian-extra"],
            "Content-Type" => $headers["Content-Type"]
        ];
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $preSignedUrl);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "PUT");
        curl_setopt($ch, CURLOPT_POSTFIELDS, $fileContent);
        curl_setopt($ch, CURLOPT_HTTPHEADER, array_map(function($key, $value) {
            return "$key: $value";
        }, array_keys($uploadHeaders), $uploadHeaders));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        if ($httpCode != 200) {
            throw new Exception("Upload failed: " . curl_error($ch));
        }
        curl_close($ch);
    }

    /**
     * Adds the file to a category.
     *
     * @param Bailian $client The client.
     * @param string $leaseId The lease ID.
     * @param string $parser The parser for the file.
     * @param string $categoryId The category ID.
     * @param string $workspaceId The workspace ID.
     * @return AddFileResponse The service response.
     */
    public static function addFile($client, $leaseId, $parser, $categoryId, $workspaceId) {
        $headers = [];
        $addFileRequest = new AddFileRequest([
            "leaseId" => $leaseId,
            "parser" => $parser,
            "categoryId" => $categoryId
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->addFileWithOptions($workspaceId, $addFileRequest, $headers, $runtime);
    }

    /**
     * Gets the basic information of a file.
     *
     * @param Bailian $client The client.
     * @param string $workspaceId The workspace ID.
     * @param string $fileId The file ID.
     * @return DescribeFileResponse The service response.
     */
    public static function describeFile($client, $workspaceId, $fileId) {
        $headers = [];
        $runtime = new RuntimeOptions([]);
        return $client->describeFileWithOptions($workspaceId, $fileId, $headers, $runtime);
    }

    /**
     * Creates a knowledge base (initializes an index).
     *
     * @param Bailian $client The client.
     * @param string $workspaceId The workspace ID.
     * @param string $fileId The file ID.
     * @param string $name The knowledge base name.
     * @param string $structureType The data structure of the knowledge base.
     * @param string $sourceType The data type of the data source. Category and file types are supported.
     * @param string $sinkType The vector storage type for the knowledge base.
     * @return CreateIndexResponse The service response.
     */
    public static function createIndex($client, $workspaceId, $fileId, $name, $structureType, $sourceType, $sinkType) {
        $headers = [];
        $createIndexRequest = new CreateIndexRequest([
            "structureType" => $structureType,
            "name" => $name,
            "sourceType" => $sourceType,
            "documentIds" => [
                $fileId
            ],
            "sinkType" => $sinkType
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->createIndexWithOptions($workspaceId, $createIndexRequest, $headers, $runtime);
    }

    /**
     * Submits an indexing task.
     *
     * @param Bailian $client The client.
     * @param string $workspaceId The workspace ID.
     * @param string $indexId The knowledge base ID.
     * @return SubmitIndexJobResponse The service response.
     */
    public static function submitIndex($client, $workspaceId, $indexId) {
        $headers = [];
        $submitIndexJobRequest = new SubmitIndexJobRequest([
            'indexId' => $indexId
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->submitIndexJobWithOptions($workspaceId, $submitIndexJobRequest, $headers, $runtime);
    }

    /**
     * Queries the status of an indexing task.
     *
     * @param Bailian $client The client.
     * @param string $workspaceId The workspace ID.
     * @param string $indexId The knowledge base ID.
     * @param string $jobId The task ID.
     * @return GetIndexJobStatusResponse The service response.
     */
    public static function getIndexJobStatus($client, $workspaceId, $jobId, $indexId) {
        $headers = [];
        $getIndexJobStatusRequest = new GetIndexJobStatusRequest([
            'indexId' => $indexId,
            'jobId' => $jobId
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->getIndexJobStatusWithOptions($workspaceId, $getIndexJobStatusRequest, $headers, $runtime);
    }

    /**
     * Creates a knowledge base.
     *
     * @param string $filePath The local path of the file.
     * @param string $workspaceId The workspace ID.
     * @param string $name The knowledge base name.
     * @return string|null The ID of the created knowledge base, or null on failure.
     */
    public static function createKnowledgeBase($filePath, $workspaceId, $name) {
        // Set default values.
        $categoryId = 'default';
        $parser = 'DASHSCOPE_DOCMIND';
        $sourceType = 'DATA_CENTER_FILE';
        $structureType = 'unstructured';
        $sinkType = 'DEFAULT';
        try {
            // Step 1: Initialize the client.
            echo "Step 1: Initialize the client\n";
            $client = self::createClient();

            // Step 2: Prepare file information.
            echo "Step 2: Prepare file information\n";
            $fileName = basename($filePath);
            echo "File name: $fileName\n";
            $fileMd5 = self::calculateMd5($filePath);
            $fileSize = self::getFileSize($filePath);

            // Step 3: Apply for an upload lease.
            echo "Step 3: Applying for an upload lease\n";
            $leaseResponse = self::applyLease($client, $categoryId, $fileName, $fileMd5, $fileSize, $workspaceId);
            $leaseId = $leaseResponse->body->data->fileUploadLeaseId;
            $uploadUrl = $leaseResponse->body->data->param->url;
            $uploadHeaders = $leaseResponse->body->data->param->headers;
            $uploadHeadersMap = json_decode(json_encode($uploadHeaders), true);

            // Step 4: Upload the file.
            echo "Step 4: Uploading the file\n";
            self::uploadFile($uploadUrl, $uploadHeadersMap, $filePath);

            // Step 5: Register the file with the service.
            echo "Step 5: Registering the file with the service\n";
            $addResponse = self::addFile($client, $leaseId, $parser, $categoryId, $workspaceId);
            $fileId = $addResponse->body->data->fileId;
            echo "File ID: $fileId\n";
            // Step 6: Check the file status.
            echo "Step 6: Checking file status\n";
            while (true) {
                $describeResponse = self::describeFile($client, $workspaceId, $fileId);
                $status = $describeResponse->body->data->status;
                echo "Current file status: $status\n";
                if ($status == 'INIT') {
                    echo "The file is pending parsing. Please wait...\n";
                } elseif ($status == 'PARSING') {
                    echo "The file is being parsed. Please wait...\n";
                } elseif ($status == 'PARSE_SUCCESS') {
                    echo "File parsed successfully.\n";
                    break;
                } else {
                    echo "Unknown file status: $status. Contact technical support.\n";
                    return null;
                }
                sleep(5);
            }

            // Step 7: Initialize the knowledge base.
            echo "Step 7: Initializing the knowledge base\n";
            $indexResponse = self::createIndex($client, $workspaceId, $fileId, $name, $structureType, $sourceType, $sinkType);
            $indexId = $indexResponse->body->data->id;

            // Step 8: Submit an indexing task.
            echo "Step 8: Submitting the indexing task\n";
            $submitResponse = self::submitIndex($client, $workspaceId, $indexId);
            $jobId = $submitResponse->body->data->id;

            // Step 9: Get the status of the indexing task.
            echo "Step 9: Checking indexing task status\n";
            while (true) {
                $getIndexJobStatusResponse = self::getIndexJobStatus($client, $workspaceId, $jobId, $indexId);
                $status = $getIndexJobStatusResponse->body->data->status;
                echo "Current indexing task status: $status\n";
                if ($status == 'COMPLETED') {
                    break;
                }
                sleep(5);
            }
            echo "Knowledge base created successfully!\n";
            return $indexId;
        } catch (Exception $e) {
            echo "An error occurred: {$e->getMessage()}\n";
            return null;
        }
    }


    /**
     * The main function.
     */
    public static function main($args){
        if (!self::checkEnvironmentVariables()) {
            echo "Environment variable check failed.\n";
            return;
        }
        $filePath = readline("Enter the local path of the file to upload (e.g., /path/to/your/file.docx): ");
        $kbName = readline("Enter a name for your knowledge base: ");
        $workspaceId = getenv('WORKSPACE_ID');
        $result = self::createKnowledgeBase($filePath, $workspaceId, $kbName);
       if ($result) {
           echo "Knowledge base ID: $result\n";
       } else {
           echo "Failed to create the knowledge base.\n";
       }
    }
}
// Assumes autoload.php is in the parent directory of the current file. Adjust the path according to your project's structure.
$path = __DIR__ . \DIRECTORY_SEPARATOR . '..' . \DIRECTORY_SEPARATOR . 'vendor' . \DIRECTORY_SEPARATOR . 'autoload.php';
if (file_exists($path)) {
    require_once $path;
}
KnowledgeBaseCreate::main(array_slice($argv, 1));
```

## Node.js

```
// This sample code is for reference only. Do not use it in a production environment.
'use strict';

const fs = require('fs');
const path = require('path');
const axios = require('axios');
const crypto = require('crypto');

const bailian20231229 = require('@alicloud/bailian20231229');
const OpenApi = require('@alicloud/openapi-client');
const Util = require('@alicloud/tea-util');
const Tea = require('@alicloud/tea-typescript');

class KbCreate {

  /**
   * Checks if the required environment variables are set.
   * @returns {boolean} - True if all required environment variables are set, false otherwise.
   */
  static checkEnvironmentVariables() {
    const requiredVars = {
      'ALIBABA_CLOUD_ACCESS_KEY_ID': 'Alibaba Cloud Access Key ID',
      'ALIBABA_CLOUD_ACCESS_KEY_SECRET': 'Alibaba Cloud Access Key Secret',
      'WORKSPACE_ID': 'Alibaba Cloud Model Studio workspace ID'
    };

    const missing = [];
    for (const [varName, desc] of Object.entries(requiredVars)) {
      if (!process.env[varName]) {
        console.error(`Error: Please set the ${varName} environment variable (${desc})`);
        missing.push(varName);
      }
    }
    return missing.length === 0;
  }

  /**
   * Calculates the MD5 hash of a file.
   * @param {string} filePath - The path to the local file.
   * @returns {Promise<string>} - The MD5 hash of the file.
   */
  static async calculateMD5(filePath) {
    const hash = crypto.createHash('md5');
    const stream = fs.createReadStream(filePath);

    return new Promise((resolve, reject) => {
      stream.on('data', chunk => hash.update(chunk));
      stream.on('end', () => resolve(hash.digest('hex')));
      stream.on('error', reject);
    });
  }

  /**
   * Gets the size of a file in bytes.
   * @param {string} filePath - The path to the local file.
   * @returns {string} - The file size as a string.
   */
  static getFileSize(filePath) {
    try {
      const stats = fs.statSync(filePath);
      return stats.size.toString();
    } catch (err) {
      console.error(`Failed to get file size: ${err.message}`);
      throw err;
    }
  }

  /**
   * Creates and configures the API client.
   * @returns {bailian20231229.default} A client instance.
   */
  static createClient() {
    const config = new OpenApi.Config({
      accessKeyId: process.env.ALIBABA_CLOUD_ACCESS_KEY_ID,
      accessKeySecret: process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET
    });
    // The endpoint below is for the public cloud. You can change the endpoint as needed.
    config.endpoint = `bailian.cn-beijing.aliyuncs.com`;
    return new bailian20231229.default(config);
  }

  /**
   * Requests a lease to upload a file.
   * @param {Bailian20231229Client} client - The client instance.
   * @param {string} categoryId - The category ID.
   * @param {string} fileName - The file name.
   * @param {string} fileMd5 - The MD5 hash of the file.
   * @param {string} fileSize - The file size in bytes.
   * @param {string} workspaceId - The workspace ID.
   * @returns {Promise<bailian20231229.ApplyFileUploadLeaseResponse>} - The response containing lease details.
   */
  static async applyLease(client, categoryId, fileName, fileMd5, fileSize, workspaceId) {
    const headers = {};
    const req = new bailian20231229.ApplyFileUploadLeaseRequest({
      md5: fileMd5,
      fileName,
      sizeInBytes: fileSize
    });
    const runtime = new Util.RuntimeOptions({});
    return await client.applyFileUploadLeaseWithOptions(
      categoryId,
      workspaceId,
      req,
      headers,
      runtime
    );
  }

  /**
   * Uploads a file to temporary storage.
   * @param {string} preSignedUrl - The presigned URL for the upload.
   * @param {Object} headers - The request headers for the upload.
   * @param {string} filePath - The path to the local file.
   */
  static async uploadFile(preSignedUrl, headers, filePath) {
    const uploadHeaders = {
      "X-bailian-extra": headers["X-bailian-extra"],
      "Content-Type": headers["Content-Type"]
    };
    const stream = fs.createReadStream(filePath);
    try {
      await axios.put(preSignedUrl, stream, { headers: uploadHeaders });
    } catch (e) {
      throw new Error(`Upload failed: ${e.message}`);
    }
  }

  /**
   * Adds a file to a category.
   * @param {Bailian20231229Client} client - The client instance.
   * @param {string} leaseId - The lease ID.
   * @param {string} parser - The parser for the file.
   * @param {string} categoryId - The category ID.
   * @param {string} workspaceId - The workspace ID.
   * @returns {Promise<bailian20231229.AddFileResponse>} - The response containing the file ID.
   */
  static async addFile(client, leaseId, parser, categoryId, workspaceId) {
    const headers = {};
    const req = new bailian20231229.AddFileRequest({
      leaseId,
      parser,
      categoryId
    });
    const runtime = new Util.RuntimeOptions({});
    return await client.addFileWithOptions(workspaceId, req, headers, runtime);
  }

  /**
   * Queries the parsing status of a file.
   * @param {Bailian20231229Client} client - The client instance.
   * @param {string} workspaceId - The workspace ID.
   * @param {string} fileId - The file ID.
   * @returns {Promise<bailian20231229.DescribeFileResponse>} - The response containing the file's status.
   */
  static async describeFile(client, workspaceId, fileId) {
    const headers = {};
    const runtime = new Util.RuntimeOptions({});
    return await client.describeFileWithOptions(workspaceId, fileId, headers, runtime);
  }

  /**
   * Initializes a knowledge base (index).
   * @param {Bailian20231229Client} client - The client instance.
   * @param {string} workspaceId - The workspace ID.
   * @param {string} fileId - The file ID.
   * @param {string} name - The name of the knowledge base.
   * @param {string} structureType - The data structure type of the knowledge base.
   * @param {string} sourceType - The data type of the source. Category and file types are supported.
   * @param {string} sinkType - The vector storage type for the knowledge base.
   * @returns {Promise<bailian20231229.CreateIndexResponse>} - The response containing the index ID.
   */
  static async createIndex(client, workspaceId, fileId, name, structureType, sourceType, sinkType) {
    const headers = {};
    const req = new bailian20231229.CreateIndexRequest({
      name,
      structureType,
      documentIds: [fileId],
      sourceType,
      sinkType
    });
    const runtime = new Util.RuntimeOptions({});
    return await client.createIndexWithOptions(workspaceId, req, headers, runtime);
  }

  /**
   * Submits an indexing job.
   * @param {Bailian20231229Client} client - The client instance.
   * @param {string} workspaceId - The workspace ID.
   * @param {string} indexId - The ID of the index (knowledge base) to process.
   * @returns {Promise<bailian20231229.SubmitIndexJobResponse>} - The response containing the job ID.
   */
  static async submitIndex(client, workspaceId, indexId) {
    const headers = {};
    const req = new bailian20231229.SubmitIndexJobRequest({ indexId });
    const runtime = new Util.RuntimeOptions({});
    return await client.submitIndexJobWithOptions(workspaceId, req, headers, runtime);
  }

  /**
   * Queries the status of an indexing job.
   * @param {Bailian20231229Client} client - The client instance.
   * @param {string} workspaceId - The workspace ID.
   * @param {string} jobId - The job ID.
   * @param {string} indexId - The ID of the index (knowledge base) to process.
   * @returns {Promise<bailian20231229.GetIndexJobStatusResponse>} - The response containing the indexing job status.
   */
  static async getIndexJobStatus(client, workspaceId, jobId, indexId) {
    const headers = {};
    const req = new bailian20231229.GetIndexJobStatusRequest({ jobId, indexId });
    const runtime = new Util.RuntimeOptions({});
    return await client.getIndexJobStatusWithOptions(workspaceId, req, headers, runtime);
  }

  /**
   * Creates a knowledge base.
   * @param {string} filePath - The path to the local file.
   * @param {string} workspaceId - The workspace ID.
   * @param {string} name - The name of the knowledge base.
   * @returns {Promise<string | null>} - The ID of the knowledge base if successful, otherwise null.
   */
  static async createKnowledgeBase(filePath, workspaceId, name) {
    const categoryId = 'default';
    const parser = 'DASHSCOPE_DOCMIND';
    const sourceType = 'DATA_CENTER_FILE';
    const structureType = 'unstructured';
    const sinkType = 'DEFAULT';

    try {
      console.log("Step 1: Initializing the client.");
      const client = this.createClient();

      console.log("Step 2: Preparing file information.");
      const fileName = path.basename(filePath);
      const fileMd5 = await this.calculateMD5(filePath);
      const fileSize = this.getFileSize(filePath);

      console.log("Step 3: Applying for an upload lease from Alibaba Cloud Model Studio");
      const leaseRes = await this.applyLease(client, categoryId, fileName, fileMd5, fileSize, workspaceId);
      const leaseId = leaseRes.body.data.fileUploadLeaseId;
      const uploadUrl = leaseRes.body.data.param.url;
      const uploadHeaders = leaseRes.body.data.param.headers;

      console.log("Step 4: Uploading the file to Alibaba Cloud Model Studio");
      await this.uploadFile(uploadUrl, uploadHeaders, filePath);

      console.log("Step 5: Adding the file to Alibaba Cloud Model Studio");
      const addRes = await this.addFile(client, leaseId, parser, categoryId, workspaceId);
      const fileId = addRes.body.data.fileId;

      console.log("Step 6: Checking the file status in Alibaba Cloud Model Studio");
      while (true) {
        const descRes = await this.describeFile(client, workspaceId, fileId);
        const status = descRes.body.data.status;
        console.log(`Current file status: ${status}`);

        if (status === 'INIT') console.log("The file is pending parsing. Please wait.");
        else if (status === 'PARSING') console.log("The file is being parsed. Please wait.");
        else if (status === 'PARSE_SUCCESS') break;
        else {
          console.error(`Unknown file status: ${status}. Please contact technical support.`);
          return null;
        }
        await this.sleep(5);
      }

      console.log("Step 7: Initializing the knowledge base in Alibaba Cloud Model Studio");
      const indexRes = await this.createIndex(client, workspaceId, fileId, name, structureType, sourceType, sinkType);
      const indexId = indexRes.body.data.id;

      console.log("Step 8: Submitting an indexing job to Alibaba Cloud Model Studio");
      const submitRes = await this.submitIndex(client, workspaceId, indexId);
      const jobId = submitRes.body.data.id;

      console.log("Step 9: Checking the status of the indexing job from Alibaba Cloud Model Studio");
      while (true) {
        const jobRes = await this.getIndexJobStatus(client, workspaceId, jobId, indexId);
        const status = jobRes.body.data.status;
        console.log(`Current indexing job status: ${status}`);
        if (status === 'COMPLETED') break;
        await this.sleep(5);
      }
      console.log("Alibaba Cloud Model Studio knowledge base created successfully!");
      return indexId;
    } catch (e) {
      console.error(`An error occurred: ${e.message}`);
      return null;
    }
  }

  /**
   * Waits for a specified number of seconds.
   * @param {number} seconds - The wait time in seconds.
   * @returns {Promise<void>}
   */
  static sleep(seconds) {
    return new Promise(resolve => setTimeout(resolve, seconds * 1000));
  }

  static async main(args) {
    if (!this.checkEnvironmentVariables()) {
      console.log("Environment variable check failed.");
      return;
    }

    const readline = require('readline').createInterface({
      input: process.stdin,
      output: process.stdout
    });

    try {
      const filePath = await new Promise((resolve, reject) => {
        readline.question("Enter the local path to the file to upload (e.g., on Linux: /path/to/Alibaba Cloud Model Studio Phone Series Introduction.docx):", (ans) => {
          ans.trim() ? resolve(ans) : reject(new Error("The path cannot be empty."));
        });
      });
      const kbName = await new Promise((resolve, reject) => {
        readline.question("Enter a name for your knowledge base:", (ans) => {
          ans.trim() ? resolve(ans) : reject(new Error("The knowledge base name cannot be empty."));
        });
      });
      const workspaceId = process.env.WORKSPACE_ID;

      const result = await KbCreate.createKnowledgeBase(filePath, workspaceId, kbName);
      if (result) console.log(`Knowledge base ID: ${result}`);
      else console.log("Failed to create the knowledge base.");
    } catch (err) {
      console.error(err.message);
    } finally {
      readline.close();
    }
  }
}

exports.KbCreate = KbCreate;
KbCreate.main(process.argv.slice(2));
```

## C#

```
// This sample code is for reference only. Do not use it in a production environment.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

using Newtonsoft.Json;
using Tea;
using Tea.Utils;


namespace AlibabaCloud.SDK.KnowledgeBase
{
    public class KnowledgeBaseCreate
    {
        /// <summary>
        /// Verifies that required environment variables are set.
        /// </summary>
        /// <returns>Returns `true` if all required environment variables are set; otherwise, `false`.</returns>
        public static bool CheckEnvironmentVariables()
        {
            var requiredVars = new Dictionary<string, string>
            {
                { "ALIBABA_CLOUD_ACCESS_KEY_ID", "Alibaba Cloud AccessKey ID" },
                { "ALIBABA_CLOUD_ACCESS_KEY_SECRET", "Alibaba Cloud AccessKey secret" },
                { "WORKSPACE_ID", "Alibaba Cloud Model Studio workspace ID" }
            };

            var missingVars = new List<string>();
            foreach (var entry in requiredVars)
            {
                string value = Environment.GetEnvironmentVariable(entry.Key);
                if (string.IsNullOrEmpty(value))
                {
                    missingVars.Add(entry.Key);
                    Console.WriteLine($"Error: Please set the {entry.Key} environment variable ({entry.Value}).");
                }
            }

            return missingVars.Count == 0;
        }

        /// <summary>
        /// Calculates the MD5 hash of a file.
        /// </summary>
        /// <param name="filePath">The local path of the file.</param>
        /// <returns>The MD5 hash of the file.</returns>
        /// <exception cref="Exception">Thrown if an error occurs during calculation.</exception>
        public static string CalculateMD5(string filePath)
        {
            using (var md5 = MD5.Create())
            {
                using (var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read))
                {
                    byte[] hashBytes = md5.ComputeHash(stream);
                    StringBuilder sb = new StringBuilder();
                    foreach (byte b in hashBytes)
                    {
                        sb.Append(b.ToString("x2"));
                    }
                    return sb.ToString();
                }
            }
        }

        /// <summary>
        /// Gets the file size in bytes.
        /// </summary>
        /// <param name="filePath">The local path of the file.</param>
        /// <returns>The file size in bytes.</returns>
        public static string GetFileSize(string filePath)
        {
            var file = new FileInfo(filePath);
            return file.Length.ToString();
        }

        /// <summary>
        /// Initializes the client.
        /// </summary>
        /// <returns>The configured client object.</returns>
        /// <exception cref="Exception">Thrown if an error occurs during initialization.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Client CreateClient()
        {
            var config = new AlibabaCloud.OpenApiClient.Models.Config
            {
                AccessKeyId = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_ID"),
                AccessKeySecret = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            };
            // This is an example public endpoint. Change it as needed.
            config.Endpoint = "bailian.cn-beijing.aliyuncs.com";
            return new AlibabaCloud.SDK.Bailian20231229.Client(config);
        }

        /// <summary>
        /// Requests a file upload lease.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="categoryId">The category ID.</param>
        /// <param name="fileName">The file name.</param>
        /// <param name="fileMd5">The MD5 hash of the file.</param>
        /// <param name="fileSize">The file size in bytes.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <returns>The response from Alibaba Cloud Model Studio.</returns>
        /// <exception cref="Exception">Thrown if an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.ApplyFileUploadLeaseResponse ApplyLease(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string categoryId,
            string fileName,
            string fileMd5,
            string fileSize,
            string workspaceId)
        {
            var headers = new Dictionary<string, string>() { };
            var applyFileUploadLeaseRequest = new AlibabaCloud.SDK.Bailian20231229.Models.ApplyFileUploadLeaseRequest
            {
                FileName = fileName,
                Md5 = fileMd5,
                SizeInBytes = fileSize
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.ApplyFileUploadLeaseWithOptions(categoryId, workspaceId, applyFileUploadLeaseRequest, headers, runtime);
        }

        /// <summary>
        /// Uploads the file to temporary storage.
        /// </summary>
        /// <param name="preSignedUrl">The URL from the upload lease.</param>
        /// <param name="headers">The request headers for the upload.</param>
        /// <param name="filePath">The local path of the file.</param>
        /// <exception cref="Exception">Thrown if an error occurs during the upload.</exception>
        public static void UploadFile(string preSignedUrl, Dictionary<string, string> headers, string filePath)
        {
            var file = new FileInfo(filePath);
            if (!File.Exists(filePath))
            {
                throw new ArgumentException($"The file does not exist or is not a regular file: {filePath}");
            }

            using (var fs = new FileStream(filePath, FileMode.Open, FileAccess.Read))
            {
                var url = new Uri(preSignedUrl);
                var conn = (HttpWebRequest)WebRequest.Create(url);
                conn.Method = "PUT";
                conn.ContentType = headers["Content-Type"];
                conn.Headers.Add("X-bailian-extra", headers["X-bailian-extra"]);

                byte[] buffer = new byte[4096];
                int bytesRead;
                using (var requestStream = conn.GetRequestStream())
                {
                    while ((bytesRead = fs.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        requestStream.Write(buffer, 0, bytesRead);
                    }
                }

                using (var response = (HttpWebResponse)conn.GetResponse())
                {
                    if (response.StatusCode != HttpStatusCode.OK)
                    {
                        throw new Exception($"Upload failed: {response.StatusCode}");
                    }
                }
            }
        }

        /// <summary>
        /// Adds the file to a category.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="leaseId">The lease ID.</param>
        /// <param name="parser">The parser to use for the file.</param>
        /// <param name="categoryId">The category ID.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <returns>The response from Alibaba Cloud Model Studio.</returns>
        /// <exception cref="Exception">Thrown if an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.AddFileResponse AddFile(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string leaseId,
            string parser,
            string categoryId,
            string workspaceId)
        {
            var headers = new Dictionary<string, string>() { };
            var addFileRequest = new AlibabaCloud.SDK.Bailian20231229.Models.AddFileRequest
            {
                LeaseId = leaseId,
                Parser = parser,
                CategoryId = categoryId
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.AddFileWithOptions(workspaceId, addFileRequest, headers, runtime);
        }

        /// <summary>
        /// Queries basic file information.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="fileId">The file ID.</param>
        /// <returns>The response from Alibaba Cloud Model Studio.</returns>
        /// <exception cref="Exception">Thrown if an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.DescribeFileResponse DescribeFile(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string workspaceId,
            string fileId)
        {
            var headers = new Dictionary<string, string>() { };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.DescribeFileWithOptions(workspaceId, fileId, headers, runtime);
        }

        /// <summary>
        /// Creates a knowledge base (initializes an index) in Alibaba Cloud Model Studio.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="fileId">The file ID.</param>
        /// <param name="name">The name of the knowledge base.</param>
        /// <param name="structureType">The data structure of the knowledge base.</param>
        /// <param name="sourceType">The data source type. Supported types include `category` and `file`.</param>
        /// <param name="sinkType">The vector storage type for the knowledge base.</param>
        /// <returns>The response from Alibaba Cloud Model Studio.</returns>
        /// <exception cref="Exception">Thrown if an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.CreateIndexResponse CreateIndex(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string workspaceId,
            string fileId,
            string name,
            string structureType,
            string sourceType,
            string sinkType)
        {
            var headers = new Dictionary<string, string>() { };
            var createIndexRequest = new AlibabaCloud.SDK.Bailian20231229.Models.CreateIndexRequest
            {
                StructureType = structureType,
                Name = name,
                SourceType = sourceType,
                SinkType = sinkType,
                DocumentIds = new List<string> { fileId }
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.CreateIndexWithOptions(workspaceId, createIndexRequest, headers, runtime);
        }

        /// <summary>
        /// Submits an indexing task to Alibaba Cloud Model Studio.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="indexId">The knowledge base ID.</param>
        /// <returns>The response from Alibaba Cloud Model Studio.</returns>
        /// <exception cref="Exception">Thrown if an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.SubmitIndexJobResponse SubmitIndex(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string workspaceId,
            string indexId)
        {
            var headers = new Dictionary<string, string>() { };
            var submitIndexJobRequest = new AlibabaCloud.SDK.Bailian20231229.Models.SubmitIndexJobRequest
            {
                IndexId = indexId
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.SubmitIndexJobWithOptions(workspaceId, submitIndexJobRequest, headers, runtime);
        }

        /// <summary>
        /// Queries the status of an indexing task.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="jobId">The task ID.</param>
        /// <param name="indexId">The knowledge base ID.</param>
        /// <returns>The response from Alibaba Cloud Model Studio.</returns>
        /// <exception cref="Exception">Thrown if an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.GetIndexJobStatusResponse GetIndexJobStatus(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string workspaceId,
            string jobId,
            string indexId)
        {
            var headers = new Dictionary<string, string>() { };
            var getIndexJobStatusRequest = new AlibabaCloud.SDK.Bailian20231229.Models.GetIndexJobStatusRequest
            {
                IndexId = indexId,
                JobId = jobId
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.GetIndexJobStatusWithOptions(workspaceId, getIndexJobStatusRequest, headers, runtime);
        }

        /// <summary>
        /// Creates a knowledge base in Alibaba Cloud Model Studio.
        /// </summary>
        /// <param name="filePath">The local path of the file.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="name">The name of the knowledge base.</param>
        /// <returns>The ID of the created knowledge base, or null if the operation fails.</returns>
        public static string CreateKnowledgeBase(string filePath, string workspaceId, string name)
        {
            // Set default values.
            string categoryId = "default";
            string parser = "DASHSCOPE_DOCMIND";
            string sourceType = "DATA_CENTER_FILE";
            string structureType = "unstructured";
            string sinkType = "DEFAULT";

            try
            {
                Console.WriteLine("Step 1: Initialize the client.");
                AlibabaCloud.SDK.Bailian20231229.Client client = CreateClient();

                Console.WriteLine("Step 2: Prepare file information.");
                var fileInfo = new FileInfo(filePath);
                string fileName = fileInfo.Name;
                string fileMd5 = CalculateMD5(filePath);
                string fileSize = GetFileSize(filePath);

                Console.WriteLine("Step 3: Request an upload lease from Alibaba Cloud Model Studio.");
                var leaseResponse = ApplyLease(client, categoryId, fileName, fileMd5, fileSize, workspaceId);
                string leaseId = leaseResponse.Body.Data.FileUploadLeaseId;
                string uploadUrl = leaseResponse.Body.Data.Param.Url;
                var uploadHeaders = leaseResponse.Body.Data.Param.Headers;

                Console.WriteLine("Step 4: Upload the file to Alibaba Cloud Model Studio.");
                // Requires the Newtonsoft.Json package.
                var uploadHeadersMap = JsonConvert.DeserializeObject<Dictionary<string, string>>(JsonConvert.SerializeObject(uploadHeaders));
                UploadFile(uploadUrl, uploadHeadersMap, filePath);

                Console.WriteLine("Step 5: Add the file to Alibaba Cloud Model Studio.");
                var addResponse = AddFile(client, leaseId, parser, categoryId, workspaceId);
                string fileId = addResponse.Body.Data.FileId;

                Console.WriteLine("Step 6: Check the file status in Alibaba Cloud Model Studio.");
                while (true)
                {
                    var describeResponse = DescribeFile(client, workspaceId, fileId);
                    string status = describeResponse.Body.Data.Status;
                    Console.WriteLine($"Current file status: {status}");

                    if (status == "INIT")
                    {
                        Console.WriteLine("The file is pending parsing. Please wait...");
                    }
                    else if (status == "PARSING")
                    {
                        Console.WriteLine("The file is being parsed. Please wait...");
                    }
                    else if (status == "PARSE_SUCCESS")
                    {
                        Console.WriteLine("File parsing complete.");
                        break;
                    }
                    else
                    {
                        Console.WriteLine($"Unknown file status: {status}. Please contact technical support.");
                        return null;
                    }
                    System.Threading.Thread.Sleep(5000);
                }

                Console.WriteLine("Step 7: Create the knowledge base in Alibaba Cloud Model Studio.");
                var indexResponse = CreateIndex(client, workspaceId, fileId, name, structureType, sourceType, sinkType);
                string indexId = indexResponse.Body.Data.Id;

                Console.WriteLine("Step 8: Submit an indexing task to Alibaba Cloud Model Studio.");
                var submitResponse = SubmitIndex(client, workspaceId, indexId);
                string jobId = submitResponse.Body.Data.Id;

                Console.WriteLine("Step 9: Check the status of the indexing task in Alibaba Cloud Model Studio.");
                while (true)
                {
                    var getStatusResponse = GetIndexJobStatus(client, workspaceId, jobId, indexId);
                    string status = getStatusResponse.Body.Data.Status;
                    Console.WriteLine($"Current indexing task status: {status}");

                    if (status == "COMPLETED")
                    {
                        break;
                    }
                    System.Threading.Thread.Sleep(5000);
                }

                Console.WriteLine("Knowledge base created successfully.");
                return indexId;

            }
            catch (Exception ex)
            {
                Console.WriteLine($"An error occurred: {ex.Message}");
                Console.WriteLine("Error details: " + ex.StackTrace);
                return null;
            }
        }

        /// <summary>
        /// The main entry point for the application.
        /// </summary>
        public static void Main(string[] args)
        {
            if (!CheckEnvironmentVariables())
            {
                return;
            }

            Console.Write("Enter the local path of the file to upload (e.g., on Linux: /path/to/Product_Introduction_for_Model_Studio_Phone_Series.docx): ");
            string filePath = Console.ReadLine();

            Console.Write("Enter a name for your knowledge base: ");
            string kbName = Console.ReadLine();

            string workspaceId = Environment.GetEnvironmentVariable("WORKSPACE_ID");
            string result = CreateKnowledgeBase(filePath, workspaceId, kbName);
            if (result != null)
            {
                Console.WriteLine($"Knowledge base ID: {result}");
            }
        }
    }
}
```

## Go

```
// This sample code is for reference only. Do not use it in a production environment.
package main

import (
	"bufio"
	"crypto/md5"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	bailian20231229 "github.com/alibabacloud-go/bailian-20231229/v2/client"
	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	util "github.com/alibabacloud-go/tea-utils/v2/service"
	"github.com/alibabacloud-go/tea/tea"
	"github.com/go-resty/resty/v2"
)

// CheckEnvironmentVariables checks for and prompts to set the required environment variables.
func CheckEnvironmentVariables() bool {
	// The required environment variables and their descriptions.
	requiredVars := map[string]string{
		"ALIBABA_CLOUD_ACCESS_KEY_ID":     "Alibaba Cloud AccessKey ID",
		"ALIBABA_CLOUD_ACCESS_KEY_SECRET": "Alibaba Cloud AccessKey secret",
		"WORKSPACE_ID":                    "Alibaba Cloud Model Studio workspace ID",
	}

	var missingVars []string
	for varName, desc := range requiredVars {
		if os.Getenv(varName) == "" {
			fmt.Printf("Error: Please set the %s environment variable (%s)\n", varName, desc)
			missingVars = append(missingVars, varName)
		}
	}

	return len(missingVars) == 0
}

// CalculateMD5 calculates the MD5 hash of a file.
//
// Parameters:
//   - filePath (string): The local path of the file.
//
// Returns:
//   - string: The MD5 hash of the file.
//   - error: The error message.
func CalculateMD5(filePath string) (_result string, _err error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	md5Hash := md5.New()
	_, err = io.Copy(md5Hash, file)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("%x", md5Hash.Sum(nil)), nil
}

// GetFileSize retrieves the file size in bytes.
//
// Parameters:
//   - filePath (string): The local path of the file.
//
// Returns:
//   - string: The file size in bytes.
//   - error: The error message.
func GetFileSize(filePath string) (_result string, _err error) {
	info, err := os.Stat(filePath)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%d", info.Size()), nil
}

// CreateClient creates and configures a client.
//
// Returns:
//   - *bailian20231229.Client: The configured client.
//   - error: The error message.
func CreateClient() (_result *bailian20231229.Client, _err error) {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	}
	// The following endpoint is a public endpoint. You can change the endpoint as needed.
	config.Endpoint = tea.String("bailian.cn-beijing.aliyuncs.com")
	_result = &bailian20231229.Client{}
	_result, _err = bailian20231229.NewClient(config)
	return _result, _err
}

// ApplyLease requests a file upload lease from the Alibaba Cloud Model Studio service.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - categoryId (string): The category ID.
//   - fileName (string): The file name.
//   - fileMD5 (string): The MD5 hash of the file.
//   - fileSize (string): The file size in bytes.
//   - workspaceId (string): The workspace ID.
//
// Returns:
//   - *bailian20231229.ApplyFileUploadLeaseResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func ApplyLease(client *bailian20231229.Client, categoryId, fileName, fileMD5 string, fileSize string, workspaceId string) (_result *bailian20231229.ApplyFileUploadLeaseResponse, _err error) {
	headers := make(map[string]*string)
	applyFileUploadLeaseRequest := &bailian20231229.ApplyFileUploadLeaseRequest{
		FileName:    tea.String(fileName),
		Md5:         tea.String(fileMD5),
		SizeInBytes: tea.String(fileSize),
	}
	runtime := &util.RuntimeOptions{}
	return client.ApplyFileUploadLeaseWithOptions(tea.String(categoryId), tea.String(workspaceId), applyFileUploadLeaseRequest, headers, runtime)
}

// UploadFile uploads a file to the Alibaba Cloud Model Studio service.
//
// Parameters:
//   - preSignedUrl (string): The URL in the file upload lease.
//   - headers (map[string]string): The request headers for the upload.
//   - filePath (string): The local path of the file.
func UploadFile(preSignedUrl string, headers map[string]string, filePath string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer file.Close()

	body, err := io.ReadAll(file)
	if err != nil {
		return err
	}

	client := resty.New()
	uploadHeaders := map[string]string{
		"X-bailian-extra": headers["X-bailian-extra"],
		"Content-Type":    headers["Content-Type"],
	}

	resp, err := client.R().
		SetHeaders(uploadHeaders).
		SetBody(body).
		Put(preSignedUrl)

	if err != nil {
		return err
	}

	if resp.IsError() {
		return fmt.Errorf("HTTP error: %d", resp.StatusCode())
	}

	return nil
}

// AddFile adds a file to a specified category in the Alibaba Cloud Model Studio service.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - leaseId (string): The lease ID.
//   - parser (string): The parser for the file.
//   - categoryId (string): The category ID.
//   - workspaceId (string): The workspace ID.
//
// Returns:
//   - *bailian20231229.AddFileResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func AddFile(client *bailian20231229.Client, leaseId, parser, categoryId, workspaceId string) (_result *bailian20231229.AddFileResponse, _err error) {
	headers := make(map[string]*string)
	addFileRequest := &bailian20231229.AddFileRequest{
		LeaseId:    tea.String(leaseId),
		Parser:     tea.String(parser),
		CategoryId: tea.String(categoryId),
	}
	runtime := &util.RuntimeOptions{}
	return client.AddFileWithOptions(tea.String(workspaceId), addFileRequest, headers, runtime)
}

// DescribeFile retrieves basic information about a file.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - workspaceId (string): The workspace ID.
//   - fileId (string): The file ID.
//
// Returns:
//   - *bailian20231229.DescribeFileResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func DescribeFile(client *bailian20231229.Client, workspaceId, fileId string) (_result *bailian20231229.DescribeFileResponse, _err error) {
	headers := make(map[string]*string)
	runtime := &util.RuntimeOptions{}
	return client.DescribeFileWithOptions(tea.String(workspaceId), tea.String(fileId), headers, runtime)
}

// CreateIndex creates a knowledge base (initializes an index) in the Alibaba Cloud Model Studio service.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - workspaceId (string): The workspace ID.
//   - fileId (string): The file ID.
//   - name (string): The knowledge base name.
//   - structureType (string): The data type of the knowledge base.
//   - sourceType (string): The type of the data source. Supports category and file types.
//   - sinkType (string): The vector storage type for the knowledge base.
//
// Returns:
//   - *bailian20231229.CreateIndexResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func CreateIndex(client *bailian20231229.Client, workspaceId, fileId, name, structureType, sourceType, sinkType string) (_result *bailian20231229.CreateIndexResponse, _err error) {
	headers := make(map[string]*string)
	createIndexRequest := &bailian20231229.CreateIndexRequest{
		StructureType: tea.String(structureType),
		Name:          tea.String(name),
		SourceType:    tea.String(sourceType),
		SinkType:      tea.String(sinkType),
		DocumentIds:   []*string{tea.String(fileId)},
	}
	runtime := &util.RuntimeOptions{}
	return client.CreateIndexWithOptions(tea.String(workspaceId), createIndexRequest, headers, runtime)
}

// SubmitIndex submits an indexing task.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - workspaceId (string): The workspace ID.
//   - indexId (string): The knowledge base ID.
//
// Returns:
//   - *bailian20231229.SubmitIndexJobResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func SubmitIndex(client *bailian20231229.Client, workspaceId, indexId string) (_result *bailian20231229.SubmitIndexJobResponse, _err error) {
	headers := make(map[string]*string)
	submitIndexJobRequest := &bailian20231229.SubmitIndexJobRequest{
		IndexId: tea.String(indexId),
	}
	runtime := &util.RuntimeOptions{}
	return client.SubmitIndexJobWithOptions(tea.String(workspaceId), submitIndexJobRequest, headers, runtime)
}

// GetIndexJobStatus queries the status of an indexing task.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - workspaceId (string): The workspace ID.
//   - jobId (string): The task ID.
//   - indexId (string): The knowledge base ID.
//
// Returns:
//   - *bailian20231229.GetIndexJobStatusResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func GetIndexJobStatus(client *bailian20231229.Client, workspaceId, jobId, indexId string) (_result *bailian20231229.GetIndexJobStatusResponse, _err error) {
	headers := make(map[string]*string)
	getIndexJobStatusRequest := &bailian20231229.GetIndexJobStatusRequest{
		JobId:   tea.String(jobId),
		IndexId: tea.String(indexId),
	}
	runtime := &util.RuntimeOptions{}
	return client.GetIndexJobStatusWithOptions(tea.String(workspaceId), getIndexJobStatusRequest, headers, runtime)
}

// CreateKnowledgeBase creates a knowledge base from a local file.
//
// Parameters:
//   - filePath (string): The local path of the file.
//   - workspaceId (string): The workspace ID.
//   - name (string): The knowledge base name.
//
// Returns:
//   - string: The ID of the created knowledge base.
//   - error: The error message.
func CreateKnowledgeBase(filePath, workspaceId, name string) (_result string, _err error) {
	categoryId := "default"
	parser := "DASHSCOPE_DOCMIND"
	sourceType := "DATA_CENTER_FILE"
	structureType := "unstructured"
	sinkType := "DEFAULT"

	fmt.Println("Step 1: Initializing the client.")
	client, err := CreateClient()
	if err != nil {
		return "", err
	}

	fmt.Println("Step 2: Preparing file information.")
	fileName := filepath.Base(filePath)
	fileMD5, err := CalculateMD5(filePath)
	if err != nil {
		return "", err
	}
	fileSizeStr, err := GetFileSize(filePath)
	if err != nil {
		return "", err
	}

	fmt.Println("Step 3: Requesting a file upload lease.")
	leaseResponse, err := ApplyLease(client, categoryId, fileName, fileMD5, fileSizeStr, workspaceId)
	if err != nil {
		return "", err
	}

	leaseId := tea.StringValue(leaseResponse.Body.Data.FileUploadLeaseId)
	uploadURL := tea.StringValue(leaseResponse.Body.Data.Param.Url)
	uploadHeaders := leaseResponse.Body.Data.Param.Headers

	jsonData, err := json.Marshal(uploadHeaders)
	if err != nil {
		return "", err
	}

	var uploadHeadersMap map[string]string
	err = json.Unmarshal(jsonData, &uploadHeadersMap)
	if err != nil {
		return "", err
	}

	fmt.Println("Step 4: Uploading the file.")
	err = UploadFile(uploadURL, uploadHeadersMap, filePath)
	if err != nil {
		return "", err
	}

	fmt.Println("Step 5: Adding the file to the service.")
	addResponse, err := AddFile(client, leaseId, parser, categoryId, workspaceId)
	if err != nil {
		return "", err
	}
	fileID := tea.StringValue(addResponse.Body.Data.FileId)

	fmt.Println("Step 6: Checking file parsing status.")
	for {
		describeResponse, err := DescribeFile(client, workspaceId, fileID)
		if err != nil {
			return "", err
		}

		status := tea.StringValue(describeResponse.Body.Data.Status)
		fmt.Printf("File status: %s\n", status)

		if status == "INIT" {
			fmt.Println("File is pending parsing. Waiting...")
		} else if status == "PARSING" {
			fmt.Println("File is being parsed. Waiting...")
		} else if status == "PARSE_SUCCESS" {
			fmt.Println("File parsed successfully.")
			break
		} else {
			fmt.Printf("Unknown file status: %s. Please contact technical support.\n", status)
			return "", fmt.Errorf("unknown document status: %s", status)
		}
		time.Sleep(5 * time.Second)
	}

	fmt.Println("Step 7: Creating the knowledge base.")
	indexResponse, err := CreateIndex(client, workspaceId, fileID, name, structureType, sourceType, sinkType)
	if err != nil {
		return "", err
	}
	indexID := tea.StringValue(indexResponse.Body.Data.Id)

	fmt.Println("Step 8: Submitting an indexing task.")
	submitResponse, err := SubmitIndex(client, workspaceId, indexID)
	if err != nil {
		return "", err
	}
	jobID := tea.StringValue(submitResponse.Body.Data.Id)

	fmt.Println("Step 9: Polling the indexing task status.")
	for {
		getIndexJobStatusResponse, err := GetIndexJobStatus(client, workspaceId, jobID, indexID)
		if err != nil {
			return "", err
		}

		status := tea.StringValue(getIndexJobStatusResponse.Body.Data.Status)
		fmt.Printf("Indexing task status: %s\n", status)

		if status == "COMPLETED" {
			break
		}
		time.Sleep(5 * time.Second)
	}

	fmt.Println("Knowledge base created successfully!")
	return indexID, nil
}

func main() {
	if !CheckEnvironmentVariables() {
		fmt.Println("Environment variable check failed.")
		return
	}
	// Create a reader for user input.
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Enter the local path of the file to upload (e.g., /path/to/your/file.docx):")
	filePath, _ := reader.ReadString('\n')
	filePath = strings.TrimSpace(filePath)
	fmt.Print("Enter a name for your knowledge base:")
	kbName, _ := reader.ReadString('\n')
	kbName = strings.TrimSpace(kbName)
	workspaceID := os.Getenv("WORKSPACE_ID")
	indexID, err := CreateKnowledgeBase(filePath, workspaceID, kbName)
	if err != nil {
		fmt.Printf("An error occurred: %v\n", err)
		return
	}
	fmt.Printf("Knowledge base created successfully. ID: %s\n", indexID)
}
```

## Retrieve from a knowledge base

**Important**

-   Before calling this example, complete the [prerequisites](#a4a15bd543can). A RAM user must also [obtain the AliyunBailianDataFullAccess policy](https://help.aliyun.com/en/model-studio/grant-data-access-permission-to-ram-user).
    
-   If you use an IDE or other development plugins, configure the `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, and `WORKSPACE_ID` variables in your development environment.
    

## Python

```
# This sample code is for reference only. Do not use it directly in a production environment.
import os

from alibabacloud_bailian20231229 import models as bailian_20231229_models
from alibabacloud_bailian20231229.client import Client as bailian20231229Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient


def check_environment_variables():
    """Checks for required environment variables and reports any that are missing."""
    required_vars = {
        'ALIBABA_CLOUD_ACCESS_KEY_ID': 'Your Alibaba Cloud AccessKey ID',
        'ALIBABA_CLOUD_ACCESS_KEY_SECRET': 'Your Alibaba Cloud AccessKey secret',
        'WORKSPACE_ID': 'Your Model Studio workspace ID'
    }
    missing_vars = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing_vars.append(var)
            print(f"Error: Set the {var} environment variable ({description}).")
    
    return len(missing_vars) == 0


def create_client() -> bailian20231229Client:
    """
    Creates and configures a client.

    Returns:
        bailian20231229Client: The configured client.
    """
    config = open_api_models.Config(
        access_key_id=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID'),
        access_key_secret=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    )
        # This is a public cloud endpoint. You can change it as needed.
    config.endpoint = 'bailian.cn-beijing.aliyuncs.com'
    return bailian20231229Client(config)


def retrieve_index(client, workspace_id, index_id, query):
    """
    Retrieves information from a specified knowledge base.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        index_id (str): The knowledge base ID.
        query (str): The search query.

    Returns:
        The response from the Model Studio service.
    """
    headers = {}
    retrieve_request = bailian_20231229_models.RetrieveRequest(
        index_id=index_id,
        query=query
    )
    runtime = util_models.RuntimeOptions()
    return client.retrieve_with_options(workspace_id, retrieve_request, headers, runtime)


def main():
    """
    Uses the Model Studio service to retrieve from a knowledge base.

    Returns:
        str or None: The retrieved text segments if the call is successful. Otherwise, None is returned.
    """
    if not check_environment_variables():
        print("Environment variable validation failed.")
        return
    try:
        print("Step 1: Create a client.")
        client = create_client()
        print("Step 2: Retrieve from the knowledge base.")
        index_id = input("Enter the knowledge base ID: ")  # This is the Data.Id value returned by the CreateIndex operation. You can also obtain it from the knowledge base page in the Model Studio console.
        query = input("Enter the search query: ")
        workspace_id = os.environ.get('WORKSPACE_ID')
        resp = retrieve_index(client, workspace_id, index_id, query)
        result = UtilClient.to_jsonstring(resp.body)
        print(result)
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == '__main__':
    main()
```

## Java

```
// This sample code is for reference only. Do not use it directly in a production environment.
import com.aliyun.bailian20231229.models.RetrieveRequest;
import com.aliyun.bailian20231229.models.RetrieveResponse;
import com.aliyun.teautil.models.RuntimeOptions;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.*;

public class KnowledgeBaseRetrieve {

    /**
     * Checks for required environment variables and reports any that are missing.
     *
     * @return true if all required environment variables are set, false otherwise.
     */
    public static boolean checkEnvironmentVariables() {
        Map<String, String> requiredVars = new HashMap<>();
        requiredVars.put("ALIBABA_CLOUD_ACCESS_KEY_ID", "Your Alibaba Cloud AccessKey ID");
        requiredVars.put("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "Your Alibaba Cloud AccessKey secret");
        requiredVars.put("WORKSPACE_ID", "Your Model Studio workspace ID");

        List<String> missingVars = new ArrayList<>();
        for (Map.Entry<String, String> entry : requiredVars.entrySet()) {
            String value = System.getenv(entry.getKey());
            if (value == null || value.isEmpty()) {
                missingVars.add(entry.getKey());
                System.out.println("Error: Set the " + entry.getKey() + " environment variable (" + entry.getValue() + ").");
            }
        }

        return missingVars.isEmpty();
    }

    /**
     * Initializes the client.
     *
     * @return The configured client object.
     */
    public static com.aliyun.bailian20231229.Client createClient() throws Exception {
        com.aliyun.teaopenapi.models.Config config = new com.aliyun.teaopenapi.models.Config()
                .setAccessKeyId(System.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"))
                .setAccessKeySecret(System.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"));
        // This is a public cloud endpoint. You can change it as needed.
        config.endpoint = "bailian.cn-beijing.aliyuncs.com";
        return new com.aliyun.bailian20231229.Client(config);
    }

    /**
     * Retrieves information from a specified knowledge base.
     *
     * @param client         The client object.
     * @param workspaceId    The workspace ID.
     * @param indexId        The knowledge base ID.
     * @param query          The search query.
     * @return               The response from the Model Studio service.
     */
    public static RetrieveResponse retrieveIndex(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId, String query) throws Exception {
        RetrieveRequest retrieveRequest = new RetrieveRequest();
        retrieveRequest.setIndexId(indexId);
        retrieveRequest.setQuery(query);
        RuntimeOptions runtime = new RuntimeOptions();
        return client.retrieveWithOptions(workspaceId, retrieveRequest, null, runtime);
    }

    /**
     * Uses the Model Studio service to retrieve from a knowledge base.
     */
    public static void main(String[] args) {
        if (!checkEnvironmentVariables()) {
            System.out.println("Environment variable validation failed.");
            return;
        }

        try {
            // Step 1: Create a client.
            System.out.println("Step 1: Create a client.");
            com.aliyun.bailian20231229.Client client = createClient();

            // Step 2: Retrieve from the knowledge base.
            System.out.println("Step 2: Retrieve from the knowledge base.");
            Scanner scanner = new Scanner(System.in);
            System.out.print("Enter the knowledge base ID: "); // This is the Data.Id value returned by the CreateIndex operation. You can also obtain it from the knowledge base page in the Model Studio console.
            String indexId = scanner.nextLine();
            System.out.print("Enter the search query: ");
            String query = scanner.nextLine();
            String workspaceId = System.getenv("WORKSPACE_ID");
            RetrieveResponse resp = retrieveIndex(client, workspaceId, indexId, query);

            // Install jackson-databind to convert the response body to a JSON string.
            ObjectMapper mapper = new ObjectMapper();
            String result = mapper.writeValueAsString(resp.getBody());
            System.out.println(result);
        } catch (Exception e) {
            System.out.println("An error occurred: " + e.getMessage());
        }
    }
}
```

## PHP

```
<?php
// This sample code is for reference only. Do not use it directly in a production environment.
namespace AlibabaCloud\SDK\Sample;

use AlibabaCloud\Dara\Models\RuntimeOptions;
use AlibabaCloud\SDK\Bailian\V20231229\Bailian;
use \Exception;

use Darabonba\OpenApi\Models\Config;
use AlibabaCloud\SDK\Bailian\V20231229\Models\RetrieveRequest;

class KnowledgeBaseRetrieve {

    /**
    * Checks for required environment variables and reports any that are missing.
    *
    * @return bool Returns true if all required environment variables are set, false otherwise.
    */
    public static function checkEnvironmentVariables() {
        $requiredVars = [
            'ALIBABA_CLOUD_ACCESS_KEY_ID' => 'Your Alibaba Cloud AccessKey ID',
            'ALIBABA_CLOUD_ACCESS_KEY_SECRET' => 'Your Alibaba Cloud AccessKey secret',
            'WORKSPACE_ID' => 'Your Model Studio workspace ID'
        ];
        $missingVars = [];
        foreach ($requiredVars as $var => $description) {
            if (!getenv($var)) {
                $missingVars[] = $var;
                echo "Error: Set the $var environment variable ($description).\n";
            }
        }
        return count($missingVars) === 0;
    }

    /**
     * Initializes the client.
     *
     * @return Bailian The configured client object.
     */
    public static function createClient(){
        $config = new Config([
            "accessKeyId" => getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"), 
            "accessKeySecret" => getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        ]);
        // This is a public cloud endpoint. You can change it as needed.
        $config->endpoint = 'bailian.cn-beijing.aliyuncs.com';
        return new Bailian($config);
    }

     /**
     * Retrieves information from a specified knowledge base.
     *
     * @param Bailian $client The client object.
     * @param string $workspaceId The workspace ID.
     * @param string $indexId The knowledge base ID.
     * @param string $query The search query.
     * @return RetrieveResponse The response from the Model Studio service.
     * @throws Exception
     */
    public static function retrieveIndex($client, $workspaceId, $indexId, $query) {
        $headers = [];
        $retrieveRequest = new RetrieveRequest([
            "query" => $query,
            "indexId" => $indexId
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->retrieveWithOptions($workspaceId, $retrieveRequest, $headers, $runtime);
    }

    /**
     * Uses the Model Studio service to retrieve from a knowledge base.
     */
    public static function main($args){
        if (!self::checkEnvironmentVariables()) {
            echo "Environment variable validation failed.\n";
            return;
        }

        try {
            // Step 1: Create a client.
            echo "Step 1: Create a client.\n";
            $client = self::createClient();

            // Step 2: Retrieve from the knowledge base.
            echo "Step 2: Retrieve from the knowledge base.\n";
            $indexId = readline("Enter the knowledge base ID: "); // This is the Data.Id value returned by the CreateIndex operation. You can also obtain it from the knowledge base page in the Model Studio console.
            $query = readline("Enter the search query: "); 
            $workspaceId = getenv("WORKSPACE_ID");
            $resp = self::retrieveIndex($client, $workspaceId, $indexId, $query);
            $result = json_encode($resp->body, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
            echo $result . "\n";
        } catch (Exception $e) {
            echo "An error occurred: " . $e->getMessage() . "\n";
        }
    }
}
// Assume that autoload.php is in the parent directory of the current code file. Adjust the path based on your project structure.
$path = __DIR__ . \DIRECTORY_SEPARATOR . '..' . \DIRECTORY_SEPARATOR . 'vendor' . \DIRECTORY_SEPARATOR . 'autoload.php';
if (file_exists($path)) {
    require_once $path;
}
KnowledgeBaseRetrieve::main(array_slice($argv, 1));
```

## Node.js

```
// This sample code is for reference only. Do not use it directly in a production environment.
'use strict';

const bailian20231229 = require('@alicloud/bailian20231229');
const OpenApi = require('@alicloud/openapi-client');
const Util = require('@alicloud/tea-util');
const Tea = require('@alicloud/tea-typescript');

class KbRetrieve {

    /**
     * Checks for required environment variables and reports any that are missing.
     * @returns {boolean} - Returns true if all required environment variables are set, false otherwise.
     */
    static checkEnvironmentVariables() {
        const requiredVars = {
            'ALIBABA_CLOUD_ACCESS_KEY_ID': 'Your Alibaba Cloud AccessKey ID',
            'ALIBABA_CLOUD_ACCESS_KEY_SECRET': 'Your Alibaba Cloud AccessKey secret',
            'WORKSPACE_ID': 'Your Model Studio workspace ID'
        };

        const missing = [];
        for (const [varName, desc] of Object.entries(requiredVars)) {
            if (!process.env[varName]) {
                console.error(`Error: Set the ${varName} environment variable (${desc}).`);
                missing.push(varName);
            }
        }
        return missing.length === 0;
    }

    /**
     * Creates and configures a client.
     * @return Client
     * @throws Exception
     */
    static createClient() {
        const config = new OpenApi.Config({
            accessKeyId: process.env.ALIBABA_CLOUD_ACCESS_KEY_ID,
            accessKeySecret: process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET
        });
        // This is a public cloud endpoint. You can change it as needed.
        config.endpoint = 'bailian.cn-beijing.aliyuncs.com';
        return new bailian20231229.default(config);
    }

    /**
     * Retrieves information from a specified knowledge base.
     * @param {bailian20231229.Client} client The client.
     * @param {string} workspaceId The workspace ID.
     * @param {string} indexId The knowledge base ID.
     * @param {string} query The search query.
     * @returns {Promise<bailian20231229.RetrieveResponse>} The response from the Model Studio service.
     */
    static async retrieveIndex(client, workspaceId, indexId, query) {
        const headers = {};
        const req = new bailian20231229.RetrieveRequest({
            indexId,
            query
        });
        const runtime = new Util.RuntimeOptions({});
        return await client.retrieveWithOptions(workspaceId, req, headers, runtime);
    }

    /**
     * Uses the Model Studio service to retrieve from a knowledge base.
     */
    static async main(args) {
        if (!this.checkEnvironmentVariables()) {
            console.log("Environment variable validation failed.");
            return;
        }

        const readline = require('readline').createInterface({
            input: process.stdin,
            output: process.stdout
        });

        try {
            console.log("Step 1: Create a client.")
            const client = this.createClient();
            
            console.log("Step 2: Retrieve from the knowledge base.")
            const indexId = await new Promise((resolve, reject) => {
                // The knowledge base ID is the Data.Id value returned by the CreateIndex operation. You can also obtain it from the knowledge base page in the Model Studio console.
                readline.question("Enter the knowledge base ID: ", (ans) => {
                    ans.trim() ? resolve(ans) : reject(new Error("The knowledge base ID cannot be empty."));
                });
            });
            const query = await new Promise((resolve, reject) => {
                readline.question("Enter the search query: ", (ans) => {
                    ans.trim() ? resolve(ans) : reject(new Error("The search query cannot be empty."));
                });
            });
            const workspaceId = process.env.WORKSPACE_ID;
            const resp = await this.retrieveIndex(client, workspaceId, indexId, query);
            const result = JSON.stringify(resp.body);
            console.log(result);
        } catch (err) {
            console.error(`An error occurred: ${err.message}`);
            return;
        } finally {
            readline.close();
        }
    }
}

exports.KbRetrieve = KbRetrieve;
KbRetrieve.main(process.argv.slice(2));

```

## C#

```
// This sample code is for reference only. Do not use it directly in a production environment.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;

using Newtonsoft.Json;
using Tea;
using Tea.Utils;


namespace AlibabaCloud.SDK.KnowledgeBase
{
    public class KnowledgeBaseRetrieve
    {
        /// <summary>
        /// Checks for required environment variables and reports any that are missing.
        /// </summary>
        /// <returns>Returns true if all required environment variables are set, false otherwise.</returns>
        public static bool CheckEnvironmentVariables()
        {
            var requiredVars = new Dictionary<string, string>
            {
                { "ALIBABA_CLOUD_ACCESS_KEY_ID", "Your Alibaba Cloud AccessKey ID" },
                { "ALIBABA_CLOUD_ACCESS_KEY_SECRET", "Your Alibaba Cloud AccessKey secret" },
                { "WORKSPACE_ID", "Your Model Studio workspace ID" }
            };

            var missingVars = new List<string>();
            foreach (var entry in requiredVars)
            {
                string value = Environment.GetEnvironmentVariable(entry.Key);
                if (string.IsNullOrEmpty(value))
                {
                    missingVars.Add(entry.Key);
                    Console.WriteLine($"Error: Set the {entry.Key} environment variable ({entry.Value}).");
                }
            }

            return missingVars.Count == 0;
        }

        /// <summary>
        /// Initializes the client.
        /// </summary>
        /// <returns>The configured client object.</returns>
        /// <exception cref="Exception">An exception is thrown if an error occurs during initialization.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Client CreateClient()
        {
            var config = new AlibabaCloud.OpenApiClient.Models.Config
            {
                AccessKeyId = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_ID"),
                AccessKeySecret = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            };
            // This is a public cloud endpoint. You can change it as needed.
            config.Endpoint = "bailian.cn-beijing.aliyuncs.com";
            return new AlibabaCloud.SDK.Bailian20231229.Client(config);
        }

        /// <summary>
        /// Retrieves information from a specified knowledge base.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="indexId">The knowledge base ID.</param>
        /// <param name="query">The search query.</param>
        /// <returns>The response from the Model Studio service.</returns>
        /// <exception cref="Exception">An exception is thrown if the call fails.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.RetrieveResponse RetrieveIndex(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string workspaceId,
            string indexId,
            string query)
        {
            var headers = new Dictionary<string, string>() { };
            var retrieveRequest = new AlibabaCloud.SDK.Bailian20231229.Models.RetrieveRequest
            {
                IndexId = indexId,
                Query = query
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.RetrieveWithOptions(workspaceId, retrieveRequest, headers, runtime);
        }

        /// <summary>
        /// Uses the Model Studio service to retrieve from a knowledge base.
        /// </summary>
        public static void Main(string[] args)
        {
            if (!CheckEnvironmentVariables())
            {
                Console.WriteLine("Environment variable validation failed.");
                return;
            }

            try
            {
                // Step 1: Create a client.
                Console.WriteLine("Step 1: Create a client.");
                AlibabaCloud.SDK.Bailian20231229.Client client = CreateClient();

                // Step 2: Retrieve from the knowledge base.
                Console.WriteLine("Step 2: Retrieve from the knowledge base.");
                Console.Write("Enter the knowledge base ID: "); // This is the Data.Id value returned by the CreateIndex operation. You can also obtain it from the knowledge base page in the Model Studio console.
                string indexId = Console.ReadLine();
                Console.Write("Enter the search query: ");
                string query = Console.ReadLine();
                string workspaceId = Environment.GetEnvironmentVariable("WORKSPACE_ID");
                AlibabaCloud.SDK.Bailian20231229.Models.RetrieveResponse resp = RetrieveIndex(client, workspaceId, indexId, query);

                // Install Newtonsoft.Json to convert the response body to a JSON string.
                var mapper = new JsonSerializerSettings { Formatting = Formatting.Indented };
                string result = JsonConvert.SerializeObject(resp.Body, mapper);
                Console.WriteLine(result);
            }
            catch (Exception e)
            {
                Console.WriteLine("An error occurred: " + e.Message);
            }
        }
    }
}
```

## Go

```
// This sample code is for reference only. Do not use it directly in a production environment.
package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	bailian20231229 "github.com/alibabacloud-go/bailian-20231229/v2/client"
	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	util "github.com/alibabacloud-go/tea-utils/v2/service"
	"github.com/alibabacloud-go/tea/tea"
)

// checkEnvironmentVariables checks for required environment variables and reports any that are missing.
func checkEnvironmentVariables() bool {
	// The required environment variables and their descriptions.
	requiredVars := map[string]string{
		"ALIBABA_CLOUD_ACCESS_KEY_ID":     "Your Alibaba Cloud AccessKey ID",
		"ALIBABA_CLOUD_ACCESS_KEY_SECRET": "Your Alibaba Cloud AccessKey secret",
		"WORKSPACE_ID":                    "Your Model Studio workspace ID",
	}

	var missingVars []string
	for varName, desc := range requiredVars {
		if os.Getenv(varName) == "" {
			fmt.Printf("Error: Set the %s environment variable (%s).\n", varName, desc)
			missingVars = append(missingVars, varName)
		}
	}

	return len(missingVars) == 0
}

// createClient creates and configures a client.
//
// Returns:
//   - *bailian20231229.Client: The configured client.
//   - error: The error message.
func createClient() (_result *bailian20231229.Client, _err error) {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	}
	// This is a public cloud endpoint. You can change it as needed.
	config.Endpoint = tea.String("bailian.cn-beijing.aliyuncs.com")
	_result = &bailian20231229.Client{}
	_result, _err = bailian20231229.NewClient(config)
	return _result, _err
}

// retrieveIndex retrieves information from a specified knowledge base.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - workspaceId (string): The workspace ID.
//   - indexId (string): The knowledge base ID.
//   - query (string): The search query.
//
// Returns:
//   - *bailian20231229.RetrieveResponse: The response from the Model Studio service.
//   - error: The error message.
func retrieveIndex(client *bailian20231229.Client, workspaceId, indexId, query string) (*bailian20231229.RetrieveResponse, error) {
	headers := make(map[string]*string)
	request := &bailian20231229.RetrieveRequest{
		IndexId: tea.String(indexId),
		Query:   tea.String(query),
	}
	runtime := &util.RuntimeOptions{}
	return client.RetrieveWithOptions(tea.String(workspaceId), request, headers, runtime)
}

// main is the entry point of the program.
func main() {
	if !checkEnvironmentVariables() {
		fmt.Println("Environment variable validation failed.")
		return
	}

	// Step 1: Create a client.
	fmt.Println("Step 1: Create a client.")
	client, err := createClient()
	if err != nil {
		fmt.Println("Failed to create a client:", err)
		return
	}

	// Step 2: Retrieve from the knowledge base.
	fmt.Println("Step 2: Retrieve from the knowledge base.")
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Enter the knowledge base ID: ") // This is the Data.Id value returned by the CreateIndex operation. You can also obtain it from the knowledge base page in the Model Studio console.
	indexId, _ := reader.ReadString('\n')
	indexId = strings.TrimSpace(indexId)
	fmt.Print("Enter the search query: ")
	query, _ := reader.ReadString('\n')
	query = strings.TrimSpace(query)
	workspaceId := os.Getenv("WORKSPACE_ID")
	resp, err := retrieveIndex(client, workspaceId, indexId, query)
	if err != nil {
		fmt.Printf("Retrieval failed: %v\n", err)
		return
	}
        jsonStr, _ := util.ToJSONString(resp.Body)
        fmt.Println(tea.StringValue(jsonStr))
}
```

## Update a knowledge base

**Important**

-   Before you call this example, complete the [prerequisites](#a4a15bd543can). If you use a RAM user, grant the [AliyunBailianDataFullAccess policy](https://help.aliyun.com/en/model-studio/grant-data-access-permission-to-ram-user) to the RAM user.
    
-   If you use an IDE or other development plugins, set the `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, and `WORKSPACE_ID` environment variables.
    

## Python

```
# This sample code is for reference only. Do not use it in a production environment.
import hashlib
import os
import time

import requests
from alibabacloud_bailian20231229 import models as bailian_20231229_models
from alibabacloud_bailian20231229.client import Client as bailian20231229Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models


def check_environment_variables():
    """Checks for required environment variables and prompts for any that are missing."""
    required_vars = {
        'ALIBABA_CLOUD_ACCESS_KEY_ID': 'Alibaba Cloud AccessKey ID',
        'ALIBABA_CLOUD_ACCESS_KEY_SECRET': 'Alibaba Cloud AccessKey secret',
        'WORKSPACE_ID': 'Alibaba Cloud Model Studio workspace ID'
    }
    missing_vars = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing_vars.append(var)
            print(f"Error: Please set the {var} environment variable ({description}).")
    
    return len(missing_vars) == 0


# Create a client.
def create_client() -> bailian20231229Client:
    """
    Creates and configures a client.

    Returns:
        bailian20231229Client: The configured client.
    """
    config = open_api_models.Config(
        access_key_id=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID'),
        access_key_secret=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    )
    # This is a public endpoint. You can change it as needed.
    config.endpoint = 'bailian.cn-beijing.aliyuncs.com'
    return bailian20231229Client(config)


def calculate_md5(file_path: str) -> str:
    """
    Calculates the MD5 hash of a file.

    Args:
        file_path (str): The local path of the file.

    Returns:
        str: The MD5 hash of the file.
    """
    md5_hash = hashlib.md5()

    # Read the file in binary mode.
    with open(file_path, "rb") as f:
        # Read the file in chunks to avoid high memory usage for large files.
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)

    return md5_hash.hexdigest()


def get_file_size(file_path: str) -> int:
    """
    Gets the size of a file in bytes.
    Args:
        file_path (str): The local path of the file.
    Returns:
        int: The file size in bytes.
    """
    return os.path.getsize(file_path)


# Apply for a file upload lease.
def apply_lease(client, category_id, file_name, file_md5, file_size, workspace_id):
    """
    Applies for a file upload lease from the Alibaba Cloud Model Studio service.

    Args:
        client (bailian20231229Client): The client.
        category_id (str): The category ID.
        file_name (str): The name of the file.
        file_md5 (str): The MD5 hash of the file.
        file_size (int): The file size in bytes.
        workspace_id (str): The workspace ID.

    Returns:
        The response from the Alibaba Cloud Model Studio service.
    """
    headers = {}
    request = bailian_20231229_models.ApplyFileUploadLeaseRequest(
        file_name=file_name,
        md_5=file_md5,
        size_in_bytes=file_size,
    )
    runtime = util_models.RuntimeOptions()
    return client.apply_file_upload_lease_with_options(category_id, workspace_id, request, headers, runtime)


# Upload the file to temporary storage.
def upload_file(pre_signed_url, headers, file_path):
    """
    Uploads a file to the Alibaba Cloud Model Studio service.
    Args:
        pre_signed_url (str): The URL from the upload lease.
        headers (dict): The request headers for the upload.
        file_path (str): The local path of the file.
    """
    with open(file_path, 'rb') as f:
        file_content = f.read()
    upload_headers = {
        "X-bailian-extra": headers["X-bailian-extra"],
        "Content-Type": headers["Content-Type"]
    }
    response = requests.put(pre_signed_url, data=file_content, headers=upload_headers)
    response.raise_for_status()


# Add the file to a category.
def add_file(client: bailian20231229Client, lease_id: str, parser: str, category_id: str, workspace_id: str):
    """
    Adds a file to a specified category in the Alibaba Cloud Model Studio service.

    Args:
        client (bailian20231229Client): The client.
        lease_id (str): The lease ID.
        parser (str): The parser to use for the file.
        category_id (str): The category ID.
        workspace_id (str): The workspace ID.

    Returns:
        The response from the Alibaba Cloud Model Studio service.
    """
    headers = {}
    request = bailian_20231229_models.AddFileRequest(
        lease_id=lease_id,
        parser=parser,
        category_id=category_id,
    )
    runtime = util_models.RuntimeOptions()
    return client.add_file_with_options(workspace_id, request, headers, runtime)


# Query the parsing status of the file.
def describe_file(client, workspace_id, file_id):
    """
    Queries the parsing status of a file.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        file_id (str): The file ID.

    Returns:
        The response from the Alibaba Cloud Model Studio service.
    """
    headers = {}
    runtime = util_models.RuntimeOptions()
    return client.describe_file_with_options(workspace_id, file_id, headers, runtime)


# Submit a job to append documents.
def submit_index_add_documents_job(client, workspace_id, index_id, file_id, source_type):
    """
    Appends a parsed file to a knowledge base.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        index_id (str): The knowledge base ID.
        file_id (str): The file ID.
        source_type(str): The data type.

    Returns:
        The response from the Alibaba Cloud Model Studio service.
    """
    headers = {}
    submit_index_add_documents_job_request = bailian_20231229_models.SubmitIndexAddDocumentsJobRequest(
        index_id=index_id,
        document_ids=[file_id],
        source_type=source_type
    )
    runtime = util_models.RuntimeOptions()
    return client.submit_index_add_documents_job_with_options(workspace_id, submit_index_add_documents_job_request,
                                                              headers, runtime)


# Wait for the document appending job to complete.
def get_index_job_status(client, workspace_id, job_id, index_id):
    """
    Queries the status of an index job.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        index_id (str): The knowledge base ID.
        job_id (str): The job ID.

    Returns:
        The response from the Alibaba Cloud Model Studio service.
    """
    headers = {}
    get_index_job_status_request = bailian_20231229_models.GetIndexJobStatusRequest(
        index_id=index_id,
        job_id=job_id
    )
    runtime = util_models.RuntimeOptions()
    return client.get_index_job_status_with_options(workspace_id, get_index_job_status_request, headers, runtime)


# Delete the old file.
def delete_index_document(client, workspace_id, index_id, file_id):
    """
    Permanently deletes one or more files from a specified knowledge base.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        index_id (str): The knowledge base ID.
        file_id (str): The file ID.

    Returns:
        The response from the Alibaba Cloud Model Studio service.
    """
    headers = {}
    delete_index_document_request = bailian_20231229_models.DeleteIndexDocumentRequest(
        index_id=index_id,
        document_ids=[file_id]
    )
    runtime = util_models.RuntimeOptions()
    return client.delete_index_document_with_options(workspace_id, delete_index_document_request, headers, runtime)


def update_knowledge_base(
        file_path: str,
        workspace_id: str,
        index_id: str,
        old_file_id: str
):
    """
    Updates a knowledge base in Alibaba Cloud Model Studio.
    Args:
        file_path (str): The local path of the updated file.
        workspace_id (str): The workspace ID.
        index_id (str): The ID of the knowledge base to update.
        old_file_id (str): The FileId of the file to be replaced.
    Returns:
        str or None: The knowledge base ID if successful, otherwise None.
    """
    # Set default values.
    category_id = 'default'
    parser = 'DASHSCOPE_DOCMIND'
    source_type = 'DATA_CENTER_FILE'
    try:
        # Step 1: Create a client.
        print("Step 1: Create a client.")
        client = create_client()
        # Step 2: Prepare file information.
        print("Step 2: Prepare file information.")
        file_name = os.path.basename(file_path)
        file_md5 = calculate_md5(file_path)
        file_size = get_file_size(file_path)
        # Step 3: Apply for an upload lease.
        print("Step 3: Apply for an upload lease from Alibaba Cloud Model Studio.")
        lease_response = apply_lease(client, category_id, file_name, file_md5, file_size, workspace_id)
        lease_id = lease_response.body.data.file_upload_lease_id
        upload_url = lease_response.body.data.param.url
        upload_headers = lease_response.body.data.param.headers
        # Step 4: Upload the file to temporary storage.
        print("Step 4: Upload the file to temporary storage.")
        upload_file(upload_url, upload_headers, file_path)
        # Step 5: Add the file to the category.
        print("Step 5: Add the file to the category.")
        add_response = add_file(client, lease_id, parser, category_id, workspace_id)
        file_id = add_response.body.data.file_id
        # Step 6: Check the file status.
        print("Step 6: Check the file status in Alibaba Cloud Model Studio.")
        while True:
            describe_response = describe_file(client, workspace_id, file_id)
            status = describe_response.body.data.status
            print(f"Current file status: {status}")
            if status == 'INIT':
                print("File is waiting to be parsed. Please wait...")
            elif status == 'PARSING':
                print("File is being parsed. Please wait...")
            elif status == 'PARSE_SUCCESS':
                print("File parsing completed successfully.")
                break
            else:
                print(f"Unknown file status: {status}. Please contact technical support.")
                return None
            time.sleep(5)
        # Step 7: Submit a job to append documents.
        print("Step 7: Submit a job to append documents.")
        index_add_response = submit_index_add_documents_job(client, workspace_id, index_id, file_id, source_type)
        job_id = index_add_response.body.data.id
        # Step 8: Wait for the indexing job to complete.
        print("Step 8: Wait for the indexing job to complete.")
        while True:
            get_index_job_status_response = get_index_job_status(client, workspace_id, job_id, index_id)
            status = get_index_job_status_response.body.data.status
            print(f"Current index job status: {status}")
            if status == 'COMPLETED':
                break
            time.sleep(5)
        # Step 9: Delete the old file.
        print("Step 9: Delete the old file.")
        delete_index_document(client, workspace_id, index_id, old_file_id)
        print("Alibaba Cloud Model Studio knowledge base updated successfully.")
        return index_id
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def main():
    if not check_environment_variables():
        print("Environment variable check failed.")
        return
    file_path = input("Enter the local path of the updated file (e.g., on a Linux system: /path/to/Alibaba_Cloud_Model_Studio_Phone_Series_Introduction.docx):")
    index_id = input("Enter the ID of the knowledge base to update: ")  # This is the Data.Id returned by the CreateIndex operation. You can also obtain it from the knowledge base page in the Alibaba Cloud Model Studio console.
    old_file_id = input("Enter the FileId of the file to be replaced: ")  # This is the FileId returned by the AddFile operation. You can also obtain it by clicking the ID icon next to the file name on the application data page in the Alibaba Cloud Model Studio console.
    workspace_id = os.environ.get('WORKSPACE_ID')
    update_knowledge_base(file_path, workspace_id, index_id, old_file_id)


if __name__ == '__main__':
    main()
```

## Java

```
// This sample code is for reference only. Do not use it in a production environment.
import com.aliyun.bailian20231229.models.*;
import com.aliyun.teautil.models.RuntimeOptions;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.File;
import java.io.FileInputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.*;

public class KnowledgeBaseUpdate {

    /**
     * Checks for required environment variables and prompts if any are missing.
     *
     * @return true if all required environment variables are set, false otherwise.
     */
    public static boolean checkEnvironmentVariables() {
        Map<String, String> requiredVars = new HashMap<>();
        requiredVars.put("ALIBABA_CLOUD_ACCESS_KEY_ID", "Alibaba Cloud AccessKey ID");
        requiredVars.put("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "Alibaba Cloud AccessKey secret");
        requiredVars.put("WORKSPACE_ID", "Alibaba Cloud Model Studio workspace ID");

        List<String> missingVars = new ArrayList<>();
        for (Map.Entry<String, String> entry : requiredVars.entrySet()) {
            String value = System.getenv(entry.getKey());
            if (value == null || value.isEmpty()) {
                missingVars.add(entry.getKey());
                System.out.println("Error: Set the " + entry.getKey() + " environment variable (" + entry.getValue() + ")");
            }
        }

        return missingVars.isEmpty();
    }

    /**
     * Creates and configures a client.
     *
     * @return The configured client.
     */
    public static com.aliyun.bailian20231229.Client createClient() throws Exception {
        com.aliyun.teaopenapi.models.Config config = new com.aliyun.teaopenapi.models.Config()
                .setAccessKeyId(System.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"))
                .setAccessKeySecret(System.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"));
        // The following is a public endpoint. Change it to match your region.
        config.endpoint = "bailian.cn-beijing.aliyuncs.com";
        return new com.aliyun.bailian20231229.Client(config);
    }

    /**
     * Calculates the MD5 hash of a file.
     *
     * @param filePath The local path of the file.
     * @return The MD5 hash of the file.
     */
    public static String calculateMD5(String filePath) throws Exception {
        MessageDigest md = MessageDigest.getInstance("MD5");
        try (FileInputStream fis = new FileInputStream(filePath)) {
            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = fis.read(buffer)) != -1) {
                md.update(buffer, 0, bytesRead);
            }
        }
        StringBuilder sb = new StringBuilder();
        for (byte b : md.digest()) {
            sb.append(String.format("%02x", b & 0xff));
        }
        return sb.toString();
    }

    /**
     * Gets the size of a file in bytes.
     *
     * @param filePath The local path of the file.
     * @return The file size in bytes.
     */
    public static String getFileSize(String filePath) {
        File file = new File(filePath);
        long fileSize = file.length();
        return String.valueOf(fileSize);
    }

    /**
     * Requests a file upload lease.
     *
     * @param client The client object.
     * @param categoryId The category ID.
     * @param fileName The file name.
     * @param fileMd5 The MD5 hash of the file.
     * @param fileSize The file size in bytes.
     * @param workspaceId The workspace ID.
     * @return The response containing the file upload lease.
     */
    public static ApplyFileUploadLeaseResponse applyLease(com.aliyun.bailian20231229.Client client, String categoryId, String fileName, String fileMd5, String fileSize, String workspaceId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.ApplyFileUploadLeaseRequest applyFileUploadLeaseRequest = new com.aliyun.bailian20231229.models.ApplyFileUploadLeaseRequest();
        applyFileUploadLeaseRequest.setFileName(fileName);
        applyFileUploadLeaseRequest.setMd5(fileMd5);
        applyFileUploadLeaseRequest.setSizeInBytes(fileSize);
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        ApplyFileUploadLeaseResponse applyFileUploadLeaseResponse = null;
        applyFileUploadLeaseResponse = client.applyFileUploadLeaseWithOptions(categoryId, workspaceId, applyFileUploadLeaseRequest, headers, runtime);
        return applyFileUploadLeaseResponse;
    }

    /**
     * Uploads a file to temporary storage.
     *
     * @param preSignedUrl The pre-signed URL from the upload lease.
     * @param headers The request headers for the upload.
     * @param filePath The local path of the file.
     * @throws Exception if an error occurs during the upload.
     */
    public static void uploadFile(String preSignedUrl, Map<String, String> headers, String filePath) throws Exception {
        File file = new File(filePath);
        if (!file.exists() || !file.isFile()) {
            throw new IllegalArgumentException("The file does not exist or is not a regular file: " + filePath);
        }

        try (FileInputStream fis = new FileInputStream(file)) {
            URL url = new URL(preSignedUrl);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("PUT");
            conn.setDoOutput(true);

            // Set the upload request headers.
            conn.setRequestProperty("X-bailian-extra", headers.get("X-bailian-extra"));
            conn.setRequestProperty("Content-Type", headers.get("Content-Type"));

            // Read and upload the file in chunks.
            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = fis.read(buffer)) != -1) {
                conn.getOutputStream().write(buffer, 0, bytesRead);
            }

            int responseCode = conn.getResponseCode();
            if (responseCode != 200) {
                throw new RuntimeException("Upload failed: " + responseCode);
            }
        }
    }

    /**
     * Adds a file to a category.
     *
     * @param client The client object.
     * @param leaseId The lease ID.
     * @param parser The parser for the file.
     * @param categoryId The category ID.
     * @param workspaceId The workspace ID.
     * @return The response containing the new file's ID.
     */
    public static AddFileResponse addFile(com.aliyun.bailian20231229.Client client, String leaseId, String parser, String categoryId, String workspaceId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.AddFileRequest addFileRequest = new com.aliyun.bailian20231229.models.AddFileRequest();
        addFileRequest.setLeaseId(leaseId);
        addFileRequest.setParser(parser);
        addFileRequest.setCategoryId(categoryId);
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        return client.addFileWithOptions(workspaceId, addFileRequest, headers, runtime);
    }

    /**
     * Gets the basic information of a file.
     *
     * @param client The client object.
     * @param workspaceId The workspace ID.
     * @param fileId The file ID.
     * @return The response containing the file's information.
     */
    public static DescribeFileResponse describeFile(com.aliyun.bailian20231229.Client client, String workspaceId, String fileId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        return client.describeFileWithOptions(workspaceId, fileId, headers, runtime);
    }

    /**
     * Submits a job to add documents to a knowledge base index.
     *
     * @param client The client.
     * @param workspaceId The workspace ID.
     * @param indexId The knowledge base ID.
     * @param fileId The file ID.
     * @param sourceType The data type.
     * @return The response containing the job ID.
     */
    public static SubmitIndexAddDocumentsJobResponse submitIndexAddDocumentsJob(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId, String fileId, String sourceType) throws Exception {
        Map<String, String> headers = new HashMap<>();
        SubmitIndexAddDocumentsJobRequest submitIndexAddDocumentsJobRequest = new SubmitIndexAddDocumentsJobRequest();
        submitIndexAddDocumentsJobRequest.setIndexId(indexId);
        submitIndexAddDocumentsJobRequest.setDocumentIds(Collections.singletonList(fileId));
        submitIndexAddDocumentsJobRequest.setSourceType(sourceType);
        RuntimeOptions runtime = new RuntimeOptions();
        return client.submitIndexAddDocumentsJobWithOptions(workspaceId, submitIndexAddDocumentsJobRequest, headers, runtime);
    }

    /**
     * Queries the status of an index job.
     *
     * @param client The client object.
     * @param workspaceId The workspace ID.
     * @param jobId The job ID.
     * @param indexId The knowledge base ID.
     * @return The response containing the index job's status.
     */
    public static GetIndexJobStatusResponse getIndexJobStatus(com.aliyun.bailian20231229.Client client, String workspaceId, String jobId, String indexId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.GetIndexJobStatusRequest getIndexJobStatusRequest = new com.aliyun.bailian20231229.models.GetIndexJobStatusRequest();
        getIndexJobStatusRequest.setIndexId(indexId);
        getIndexJobStatusRequest.setJobId(jobId);
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        GetIndexJobStatusResponse getIndexJobStatusResponse = null;
        getIndexJobStatusResponse = client.getIndexJobStatusWithOptions(workspaceId, getIndexJobStatusRequest, headers, runtime);
        return getIndexJobStatusResponse;
    }

    /**
     * Deletes documents from a knowledge base index.
     *
     * @param client The client.
     * @param workspaceId The workspace ID.
     * @param indexId The knowledge base ID.
     * @param fileId The file ID.
     * @return The response from the Alibaba Cloud Model Studio service.
     */
    public static DeleteIndexDocumentResponse deleteIndexDocument(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId, String fileId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        DeleteIndexDocumentRequest deleteIndexDocumentRequest = new DeleteIndexDocumentRequest();
        deleteIndexDocumentRequest.setIndexId(indexId);
        deleteIndexDocumentRequest.setDocumentIds(Collections.singletonList(fileId));
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        return client.deleteIndexDocumentWithOptions(workspaceId, deleteIndexDocumentRequest, headers, runtime);
    }

    /**
     * Updates a knowledge base by using the Alibaba Cloud Model Studio service.
     *
     * @param filePath The local path of the updated file.
     * @param workspaceId The workspace ID.
     * @param indexId The ID of the knowledge base to update.
     * @param oldFileId The ID of the file to be replaced.
     * @return The indexId if the update is successful; otherwise, null. */ public static String updateKnowledgeBase(String filePath, String workspaceId, String indexId, String oldFileId) { // Set default values. String categoryId = "default"; String parser = "DASHSCOPE_DOCMIND"; String sourceType = "DATA_CENTER_FILE"; try { // Step 1: Initialize the client. System.out.println("Step 1: Create a client."); com.aliyun.bailian20231229.Client client = createClient(); // Step 2: Prepare file information for the updated file. System.out.println("Step 2: Prepare file information."); String fileName = Paths.get(filePath).getFileName().toString(); String fileMd5 = calculateMD5(filePath); String fileSize = getFileSize(filePath); // Step 3: Request an upload lease. System.out.println("Step 3: Request an upload lease from Alibaba Cloud Model Studio."); ApplyFileUploadLeaseResponse leaseResponse = applyLease(client, categoryId, fileName, fileMd5, fileSize, workspaceId); String leaseId = leaseResponse.getBody().getData().getFileUploadLeaseId(); String uploadUrl = leaseResponse.getBody().getData().getParam().getUrl(); Object uploadHeaders = leaseResponse.getBody().getData().getParam().getHeaders(); // Step 4: Upload the file to temporary storage. System.out.println("Step 4: Upload the file to temporary storage."); // Install the jackson-databind dependency. // Convert the uploadHeaders object to a Map. ObjectMapper mapper = new ObjectMapper(); Map<String, String> uploadHeadersMap = (Map<String, String>) mapper.readValue(mapper.writeValueAsString(uploadHeaders), Map.class); uploadFile(uploadUrl, uploadHeadersMap, filePath); // Step 5: Add the file to the category. System.out.println("Step 5: Add the file to the category."); AddFileResponse addResponse = addFile(client, leaseId, parser, categoryId, workspaceId); String fileId = addResponse.getBody().getData().getFileId(); // Step 6: Check the status of the updated file. System.out.println("Step 6: Check the file status in Alibaba Cloud Model Studio."); while (true) { DescribeFileResponse describeResponse = describeFile(client, workspaceId, fileId); String status = describeResponse.getBody().getData().getStatus(); System.out.println("Current file status: " + status); if ("INIT".equals(status)) { System.out.println("The file is pending parsing. Please wait..."); } else if ("PARSING".equals(status)) { System.out.println("The file is being parsed. Please wait..."); } else if ("PARSE_SUCCESS".equals(status)) { System.out.println("The file is parsed successfully."); break; } else { System.out.println("Unknown file status: " + status + ". Contact technical support."); return null; } Thread.sleep(5000); } // Step 7: Submit a job to add the file to the index. System.out.println("Step 7: Submit a job to add the file to the index."); SubmitIndexAddDocumentsJobResponse indexAddResponse = submitIndexAddDocumentsJob(client, workspaceId, indexId, fileId, sourceType); String jobId = indexAddResponse.getBody().getData().getId(); // Step 8: Wait for the job to complete. System.out.println("Step 8: Wait for the job to complete."); while (true) { GetIndexJobStatusResponse jobStatusResponse = getIndexJobStatus(client, workspaceId, jobId, indexId); String status = jobStatusResponse.getBody().getData().getStatus(); System.out.println("Current index job status: " + status); if ("COMPLETED".equals(status)) { break; } Thread.sleep(5000); } // Step 9: Delete the old document from the index. System.out.println("Step 9: Delete the old document from the index."); deleteIndexDocument(client, workspaceId, indexId, oldFileId); System.out.println("The Alibaba Cloud Model Studio knowledge base is updated successfully."); return indexId; } catch (Exception e) { System.out.println("An error occurred: " + e.getMessage()); return null; } } /** * The main method. */ public static void main(String[] args) { if (!checkEnvironmentVariables()) { System.out.println("Environment variable check failed."); return; } Scanner scanner = new Scanner(System.in); System.out.print("Enter the local path of the updated file to upload (for example, /home/user/Alibaba_Cloud_Model_Studio_Phone_Series_Introduction.docx on a Linux system):"); String filePath = scanner.nextLine(); System.out.print("Enter the ID of the knowledge base to update:"); // This is the Data.Id returned by the CreateIndex operation. You can also obtain the ID on the knowledge base page in the Alibaba Cloud Model Studio console. String indexId = scanner.nextLine(); System.out.print("Enter the FileID of the file to be replaced:"); // This is the FileId returned by the AddFile operation. You can also obtain the file ID by clicking the ID icon next to the file name on the application data page in the Alibaba Cloud Model Studio console. String oldFileId = scanner.nextLine(); String workspaceId = System.getenv("WORKSPACE_ID"); String result = updateKnowledgeBase(filePath, workspaceId, indexId, oldFileId); if (result != null) { System.out.println("Knowledge base updated successfully. Knowledge base ID: " + result); } else { System.out.println("Failed to update the knowledge base."); } } } 
```

## PHP

```
<?php
// This sample code is for reference only. Do not use it in a production environment.
namespace AlibabaCloud\SDK\Sample;

use AlibabaCloud\Dara\Models\RuntimeOptions;
use AlibabaCloud\SDK\Bailian\V20231229\Bailian;
use AlibabaCloud\SDK\Bailian\V20231229\Models\AddFileRequest;
use \Exception;

use Darabonba\OpenApi\Models\Config;
use AlibabaCloud\SDK\Bailian\V20231229\Models\ApplyFileUploadLeaseRequest;
use AlibabaCloud\SDK\Bailian\V20231229\Models\DeleteIndexDocumentRequest;
use AlibabaCloud\SDK\Bailian\V20231229\Models\GetIndexJobStatusRequest;
use AlibabaCloud\SDK\Bailian\V20231229\Models\SubmitIndexAddDocumentsJobRequest;

class KnowledgeBaseUpdate {

    /**
    * Checks if the required environment variables are set.
    *
    * @return bool Returns true if all required environment variables are set, false otherwise.
    */
    public static function checkEnvironmentVariables() {
        $requiredVars = [
            'ALIBABA_CLOUD_ACCESS_KEY_ID' => 'Alibaba Cloud AccessKey ID',
            'ALIBABA_CLOUD_ACCESS_KEY_SECRET' => 'Alibaba Cloud AccessKey secret',
            'WORKSPACE_ID' => 'Alibaba Cloud Model Studio workspace ID'
        ];
        $missingVars = [];
        foreach ($requiredVars as $var => $description) {
            if (!getenv($var)) {
                $missingVars[] = $var;
                echo "Error: Please set the $var environment variable ($description)\n";
            }
        }
        return count($missingVars) === 0;
    }

    /**
     * Calculates the MD5 hash of a file.
     *
     * @param string $filePath The local path of the file.
     * @return string The MD5 hash of the file.
     */
    public static function calculateMd5($filePath) {
        $md5Hash = hash_init("md5");
        $handle = fopen($filePath, "rb");
        while (!feof($handle)) {
            $chunk = fread($handle, 4096);
            hash_update($md5Hash, $chunk);
        }
        fclose($handle);
        return hash_final($md5Hash);
    }

    /**
     * Gets the size of a file in bytes.
     *
     * @param string $filePath The local path of the file.
     * @return int The file size in bytes.
     */
    public static function getFileSize($filePath) {
        return (string)filesize($filePath);
    }

    /**
     * Initializes the client.
     *
     * @return Bailian The configured client object.
     */
    public static function createClient(){
        $config = new Config([
            "accessKeyId" => getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"), 
            "accessKeySecret" => getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        ]);
        // The following endpoint is for the China (Beijing) region. You can change the endpoint as needed.
        $config->endpoint = 'bailian.cn-beijing.aliyuncs.com';
        return new Bailian($config);
    }

    /**
     * Requests a file upload lease.
     *
     * @param Bailian $client The client.
     * @param string $categoryId The category ID.
     * @param string $fileName The file name.
     * @param string $fileMd5 The MD5 hash of the file.
     * @param int $fileSize The file size in bytes.
     * @param string $workspaceId The workspace ID.
     * @return ApplyFileUploadLeaseResponse The response from the Alibaba Cloud Model Studio service.
     */
    public static function applyLease($client, $categoryId, $fileName, $fileMd5, $fileSize, $workspaceId) {
        $headers = [];
        $applyFileUploadLeaseRequest = new ApplyFileUploadLeaseRequest([
            "fileName" => $fileName,
            "md5" => $fileMd5,
            "sizeInBytes" => $fileSize
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->applyFileUploadLeaseWithOptions($categoryId, $workspaceId, $applyFileUploadLeaseRequest, $headers, $runtime);
    }

    /**
     * Uploads the file to temporary storage.
    *
    * @param string $preSignedUrl The URL in the upload lease.
    * @param array $headers The request headers for the upload.
    * @param string $filePath The local path of the file.
    */
    public static function uploadFile($preSignedUrl, $headers, $filePath) {
        $fileContent = file_get_contents($filePath);
        // Set the upload request headers.
        $uploadHeaders = [
            "X-bailian-extra" => $headers["X-bailian-extra"],
            "Content-Type" => $headers["Content-Type"]
        ];
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $preSignedUrl);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "PUT");
        curl_setopt($ch, CURLOPT_POSTFIELDS, $fileContent);
        curl_setopt($ch, CURLOPT_HTTPHEADER, array_map(function($key, $value) {
            return "$key: $value";
        }, array_keys($uploadHeaders), $uploadHeaders));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        if ($httpCode != 200) {
            throw new Exception("Upload failed: " . curl_error($ch));
        }
        curl_close($ch);
    }

    /**
     * Adds the file to a category.
     *
     * @param Bailian $client The client.
     * @param string $leaseId The lease ID.
     * @param string $parser The parser for the file.
     * @param string $categoryId The category ID.
     * @param string $workspaceId The workspace ID.
     * @return AddFileResponse The response from the Alibaba Cloud Model Studio service.
     */
    public static function addFile($client, $leaseId, $parser, $categoryId, $workspaceId) {
        $headers = [];
        $addFileRequest = new AddFileRequest([
            "leaseId" => $leaseId,
            "parser" => $parser,
            "categoryId" => $categoryId
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->addFileWithOptions($workspaceId, $addFileRequest, $headers, $runtime);
    }

    /**
     * Gets information about a file.
     *
     * @param Bailian $client The client.
     * @param string $workspaceId The workspace ID.
     * @param string $fileId The file ID.
     * @return DescribeFileResponse The response from the Alibaba Cloud Model Studio service.
     */
    public static function describeFile($client, $workspaceId, $fileId) {
        $headers = [];
        $runtime = new RuntimeOptions([]);
        return $client->describeFileWithOptions($workspaceId, $fileId, $headers, $runtime);
    }

    /**
     * Appends a parsed file to a knowledge base.
     *
     * @param Bailian $client The client object.
     * @param string $workspaceId The workspace ID.
     * @param string $indexId The knowledge base ID.
     * @param string $fileId The file ID.
     * @param string $sourceType The data type.
     * @return SubmitIndexAddDocumentsJobResponse The response from the Alibaba Cloud Model Studio service.
     * @throws Exception
     */
    public static function submitIndexAddDocumentsJob($client, $workspaceId, $indexId, $fileId, $sourceType) {
        $headers = [];
        $submitIndexAddDocumentsJobRequest = new SubmitIndexAddDocumentsJobRequest([
            "indexId" =>$indexId,
            "sourceType" => $sourceType,
            "documentIds" => [
                $fileId
            ]
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->submitIndexAddDocumentsJobWithOptions($workspaceId, $submitIndexAddDocumentsJobRequest, $headers, $runtime);
    }

    /**
     * Queries the status of an index job.
     *
     * @param Bailian $client The client.
     * @param string $workspaceId The workspace ID.
     * @param string $indexId The knowledge base ID.
     * @param string $jobId The job ID.
     * @return GetIndexJobStatusResponse The response from the Alibaba Cloud Model Studio service.
     */
    public static function getIndexJobStatus($client, $workspaceId, $jobId, $indexId) {
        $headers = [];
        $getIndexJobStatusRequest = new GetIndexJobStatusRequest([
            'indexId' => $indexId,
            'jobId' => $jobId
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->getIndexJobStatusWithOptions($workspaceId, $getIndexJobStatusRequest, $headers, $runtime);
    }

    /**
     * Permanently deletes a file from a knowledge base.
     *
     * @param Bailian $client The client object.
     * @param string $workspaceId The workspace ID.
     * @param string $indexId The knowledge base ID.
     * @param string $fileId The file ID.
     * @return mixed The response from the Alibaba Cloud Model Studio service.
     * @throws Exception
     */
    public static function deleteIndexDocument($client, $workspaceId, $indexId, $fileId) {
        $headers = [];
        $deleteIndexDocumentRequest = new DeleteIndexDocumentRequest([
            "indexId" => $indexId,
            "documentIds" => [
                $fileId
            ]
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->deleteIndexDocumentWithOptions($workspaceId, $deleteIndexDocumentRequest, $headers, $runtime);
    }

    /**
     * Updates a knowledge base.
     *
     * @param string $filePath The local path of the updated file.
     * @param string $workspaceId The workspace ID.
     * @param string $indexId The ID of the knowledge base to update.
     * @param string $oldFileId The FileID of the file to update.
     * @return string| null The knowledge base ID on success, or null on failure.
     */
    public static function updateKnowledgeBase($filePath, $workspaceId, $indexId, $oldFileId) {
        $categoryId = "default";
        $parser = "DASHSCOPE_DOCMIND";
        $sourceType = "DATA_CENTER_FILE";

        try {
            // Step 1: Create a client.
            echo "Step 1: Create a client.\n";
            $client = self::createClient();

            // Step 2: Prepare file information.
            echo "Step 2: Prepare file information.\n";
            $fileName = basename($filePath);
            $fileMd5 = self::calculateMD5($filePath);
            $fileSize = self::getFileSize($filePath);

            // Step 3: Request an upload lease.
            echo "Step 3: Request an upload lease.\n";
            $leaseResponse = self::applyLease($client, $categoryId, $fileName, $fileMd5, $fileSize, $workspaceId);
            $leaseId = $leaseResponse->body->data->fileUploadLeaseId;
            $uploadUrl = $leaseResponse->body->data->param->url;
            $uploadHeaders = $leaseResponse->body->data->param->headers;
            $uploadHeadersMap = json_decode(json_encode($uploadHeaders), true);

            // Step 4: Upload the file to temporary storage.
            echo "Step 4: Upload the file to temporary storage.\n";
            self::uploadFile($uploadUrl, $uploadHeadersMap, $filePath);

            // Step 5: Add the file to the category.
            echo "Step 5: Add the file to the category.\n";
            $addResponse = self::addFile($client, $leaseId, $parser, $categoryId, $workspaceId);
            $fileId = $addResponse->body->data->fileId;

            // Step 6: Check the file status.
            echo "Step 6: Check the file status.\n";
            while (true) {
                $describeResponse = self::describeFile($client, $workspaceId, $fileId);
                $status = $describeResponse->body->data->status;
                echo "Current file status: " . $status . "\n";

                if ($status === "INIT") {
                    echo "The file is pending parsing. Please wait...\n";
                } elseif ($status === "PARSING") {
                    echo "The file is being parsed. Please wait...\n";
                } elseif ($status === "PARSE_SUCCESS") {
                    echo "File parsed successfully.\n";
                    break;
                } else {
                    echo "Unknown file status: " . $status . ". Please contact technical support.\n";
                    return null;
                }
                sleep(5);
            }

            // Step 7: Submit an index job to add the file.
            echo "Step 7: Submit an index job to add the file.\n";
            $indexAddResponse = self::submitIndexAddDocumentsJob($client, $workspaceId, $indexId, $fileId, $sourceType);
            $jobId = $indexAddResponse->body->data->id;

            // Step 8: Wait for the index job to complete.
            echo "Step 8: Wait for the index job to complete.\n";
            while (true) {
                $jobStatusResponse = self::getIndexJobStatus($client, $workspaceId, $jobId, $indexId);
                $status = $jobStatusResponse->body->data->status;
                echo "Current index job status: " . $status . "\n";

                if ($status === "COMPLETED") {
                    break;
                }
                sleep(5);
            }

            // Step 9: Delete the old file.
            echo "Step 9: Delete the old file.\n";
            self::deleteIndexDocument($client, $workspaceId, $indexId, $oldFileId);

            echo "Knowledge base updated successfully.\n";
            return $indexId;

        } catch (Exception $e) {
            echo "An error occurred: " . $e->getMessage() . "\n";
            return null;
        }
    }


    /**
     * Main function to orchestrate the knowledge base update process.
     */
    public static function main($args){
        if (!self::checkEnvironmentVariables()) {
            echo "The environment variable check failed.\n";
            return;
        }
        $filePath = readline("Enter the local path of the file to upload (e.g., /path/to/your_file.docx):");
        $indexId = readline("Enter the ID of the knowledge base to update:"); // This is the Data.Id returned by the CreateIndex operation. You can also get the ID on the knowledge base page in the Model Studio console.
        $oldFileId = readline("Enter the FileID of the file to update:"); // This is the FileId returned by the AddFile operation. You can also get the file ID by clicking the ID icon next to the file name on the application data page in the Model Studio console.
        $workspaceId = getenv('WORKSPACE_ID');
        $result = self::updateKnowledgeBase($filePath, $workspaceId, $indexId, $oldFileId);

        if ($result !== null) {
            echo "Knowledge base updated successfully. ID: " . $result . "\n";
        } else {
            echo "Failed to update the knowledge base.\n";
        }
    }
}
// This script assumes autoload.php is in the parent directory. Adjust the path for your project structure.
$path = __DIR__ . \DIRECTORY_SEPARATOR . '..' . \DIRECTORY_SEPARATOR . 'vendor' . \DIRECTORY_SEPARATOR . 'autoload.php';
if (file_exists($path)) {
    require_once $path;
}
KnowledgeBaseUpdate::main(array_slice($argv, 1));
```

## Node.js

```
// This sample code is for reference only. Do not use it in a production environment.
'use strict';

const fs = require('fs');
const path = require('path');
const axios = require('axios');
const crypto = require('crypto');

const bailian20231229 = require('@alicloud/bailian20231229');
const OpenApi = require('@alicloud/openapi-client');
const Util = require('@alicloud/tea-util');
const Tea = require('@alicloud/tea-typescript');

class KbUpdate {

    /**
     * Verifies that the required environment variables are set.
     * @returns {boolean} - Returns true if all required environment variables are set; otherwise, returns false.
     */
    static checkEnvironmentVariables() {
        const requiredVars = {
            'ALIBABA_CLOUD_ACCESS_KEY_ID': 'Alibaba Cloud AccessKey ID',
            'ALIBABA_CLOUD_ACCESS_KEY_SECRET': 'Alibaba Cloud AccessKey Secret',
            'WORKSPACE_ID': 'Alibaba Cloud Model Studio workspace ID'
        };

        const missing = [];
        for (const [varName, desc] of Object.entries(requiredVars)) {
            if (!process.env[varName]) {
                console.error(`Error: Please set the ${varName} environment variable (${desc}).`);
                missing.push(varName);
            }
        }
        return missing.length === 0;
    }

    /**
     * Calculates the MD5 hash of a file.
     * @param {string} filePath - The local path to the file.
     * @returns {Promise<string>} - The MD5 hash of the file.
     */
    static async calculateMD5(filePath) {
        const hash = crypto.createHash('md5');
        const stream = fs.createReadStream(filePath);

        return new Promise((resolve, reject) => {
            stream.on('data', chunk => hash.update(chunk));
            stream.on('end', () => resolve(hash.digest('hex')));
            stream.on('error', reject);
        });
    }

    /**
     * Gets the size of a file in bytes and returns it as a string.
     * @param {string} filePath - The local path to the file.
     * @returns {string} - The file size, for example, "123456".
     */
    static getFileSize(filePath) {
        try {
            const stats = fs.statSync(filePath);
            return stats.size.toString();
        } catch (err) {
            console.error(`Failed to get file size: ${err.message}`);
            throw err;
        }
    }

    /**
     * Creates and configures a client.
     * @return Client
     * @throws Exception
     */
    static createClient() {
        const config = new OpenApi.Config({
            accessKeyId: process.env.ALIBABA_CLOUD_ACCESS_KEY_ID,
            accessKeySecret: process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET
        });
        // This endpoint is for the public cloud in the China (Beijing) region. Change it as needed.
        config.endpoint = `bailian.cn-beijing.aliyuncs.com`;
        return new bailian20231229.default(config);
    }

    /**
     * Requests a file upload lease.
     * @param {Bailian20231229Client} client - The client.
     * @param {string} categoryId - The category ID.
     * @param {string} fileName - The file name.
     * @param {string} fileMd5 - The MD5 hash of the file.
     * @param {string} fileSize - The file size in bytes.
     * @param {string} workspaceId - The workspace ID.
     * @returns {Promise<bailian20231229.ApplyFileUploadLeaseResponse>} - The response from the Alibaba Cloud Model Studio service.
     */
    static async applyLease(client, categoryId, fileName, fileMd5, fileSize, workspaceId) {
        const headers = {};
        const req = new bailian20231229.ApplyFileUploadLeaseRequest({
            md5: fileMd5,
            fileName,
            sizeInBytes: fileSize
        });
        const runtime = new Util.RuntimeOptions({});
        return await client.applyFileUploadLeaseWithOptions(
            categoryId,
            workspaceId,
            req,
            headers,
            runtime
        );
    }

    /**
     * Uploads the file to temporary storage.
     * @param {string} preSignedUrl - The pre-signed URL from the upload lease.
     * @param {Object} headers - The request headers for the upload.
     * @param {string} filePath - The local path to the file.
     */
    static async uploadFile(preSignedUrl, headers, filePath) {
        const uploadHeaders = {
            "X-bailian-extra": headers["X-bailian-extra"],
            "Content-Type": headers["Content-Type"]
        };
        const stream = fs.createReadStream(filePath);
        try {
            await axios.put(preSignedUrl, stream, { headers: uploadHeaders });
        } catch (e) {
            throw new Error(`Upload failed: ${e.message}`);
        }
    }

    /**
     * Adds a file to a category.
     * @param {Bailian20231229Client} client - The client.
     * @param {string} leaseId - The lease ID.
     * @param {string} parser - The parser for the file.
     * @param {string} categoryId - The category ID.
     * @param {string} workspaceId - The workspace ID.
     * @returns {Promise<bailian20231229.AddFileResponse>} - The response from the Alibaba Cloud Model Studio service.
     */
    static async addFile(client, leaseId, parser, categoryId, workspaceId) {
        const headers = {};
        const req = new bailian20231229.AddFileRequest({
            leaseId,
            parser,
            categoryId
        });
        const runtime = new Util.RuntimeOptions({});
        return await client.addFileWithOptions(workspaceId, req, headers, runtime);
    }

    /**
     * Queries the parsing status of a file.
     * @param {Bailian20231229Client} client - The client.
     * @param {string} workspaceId - The workspace ID.
     * @param {string} fileId - The file ID.
     * @returns {Promise<bailian20231229.DescribeFileResponse>} - The response from the Alibaba Cloud Model Studio service.
     */
    static async describeFile(client, workspaceId, fileId) {
        const headers = {};
        const runtime = new Util.RuntimeOptions({});
        return await client.describeFileWithOptions(workspaceId, fileId, headers, runtime);
    }

    /**
     * Submits a job to add documents to an index.
     * @param {Bailian20231229Client} client - The client.
     * @param {string} workspaceId - The workspace ID.
     * @param {string} indexId - The knowledge base ID.
     * @param {string} fileId - The file ID.
     * @param {string} sourceType - The data type.
     * @returns {Promise<bailian20231229.SubmitIndexAddDocumentsJobResponse>} - The response from the Alibaba Cloud Model Studio service.
     */
    static async submitIndexAddDocumentsJob(client, workspaceId, indexId, fileId, sourceType) {
        const headers = {};
        const req = new bailian20231229.SubmitIndexAddDocumentsJobRequest({
            indexId,
            documentIds: [fileId],
            sourceType,
        });
        const runtime = new Util.RuntimeOptions({});
        return await client.submitIndexAddDocumentsJobWithOptions(workspaceId, req, headers, runtime);
    }

    /**
     * Queries the status of an index job.
     * @param {Bailian20231229Client} client - The client.
     * @param {string} workspaceId - The workspace ID.
     * @param {string} jobId - The job ID.
     * @param {string} indexId - The knowledge base ID.
     * @returns {Promise<bailian20231229.GetIndexJobStatusResponse>} - The response from the Alibaba Cloud Model Studio service.
     */
    static async getIndexJobStatus(client, workspaceId, jobId, indexId) {
        const headers = {};
        const req = new bailian20231229.GetIndexJobStatusRequest({ jobId, indexId });
        const runtime = new Util.RuntimeOptions({});
        return await client.getIndexJobStatusWithOptions(workspaceId, req, headers, runtime);
    }

    /**
     * Deletes a document from the knowledge base index.
     * @param {Bailian20231229Client} client - The client.
     * @param {string} workspaceId - The workspace ID.
     * @param {string} indexId - The knowledge base ID.
     * @param {string} fileId - The ID of the document to delete.
     * @returns {Promise<bailian20231229.DeleteIndexDocumentResponse>} - The response from the Alibaba Cloud Model Studio service.
     */
    static async deleteIndexDocument(client, workspaceId, indexId, fileId) {
        const headers = {};
        const req = new bailian20231229.DeleteIndexDocumentRequest({
            indexId,
            documentIds: [fileId],
        });
        const runtime = new Util.RuntimeOptions({});
        return await client.deleteIndexDocumentWithOptions(workspaceId, req, headers, runtime);
    }

    /**
     * Updates a knowledge base in Alibaba Cloud Model Studio.
     * @param {string} filePath - The local path to the updated file.
     * @param {string} workspaceId - The workspace ID.
     * @param {string} indexId - The ID of the knowledge base to update.
     * @param {string} oldFileId - The ID of the file to replace.
     * @returns {Promise<string | null>} - The knowledge base ID if successful; otherwise, null.
     */
    static async updateKnowledgeBase(filePath, workspaceId, indexId, oldFileId) {
        const categoryId = 'default';
        const parser = 'DASHSCOPE_DOCMIND';
        const sourceType = 'DATA_CENTER_FILE';

        try {
            console.log("Step 1: Creating a client.");
            const client = this.createClient();

            console.log("Step 2: Preparing file information.");
            const fileName = path.basename(filePath);
            const fileMd5 = await this.calculateMD5(filePath);
            const fileSize = this.getFileSize(filePath);

            console.log("Step 3: Applying for a file upload lease from Alibaba Cloud Model Studio.");
            const leaseRes = await this.applyLease(client, categoryId, fileName, fileMd5, fileSize, workspaceId);
            const leaseId = leaseRes.body.data.fileUploadLeaseId;
            const uploadUrl = leaseRes.body.data.param.url;
            const uploadHeaders = leaseRes.body.data.param.headers;

            console.log("Step 4: Uploading the file to temporary storage.");
            await this.uploadFile(uploadUrl, uploadHeaders, filePath);

            console.log("Step 5: Adding the file to the category.");
            const addRes = await this.addFile(client, leaseId, parser, categoryId, workspaceId);
            const fileId = addRes.body.data.fileId;

            console.log("Step 6: Checking the file status in Alibaba Cloud Model Studio.");
            while (true) {
                const descRes = await this.describeFile(client, workspaceId, fileId);
                const status = descRes.body.data.status;
                console.log(`Current file status: ${status}`);

                if (status === 'INIT') {
                    console.log("File is awaiting parsing. Please wait...");
                } else if (status === 'PARSING') {
                    console.log("File is being parsed. Please wait...");
                } else if (status === 'PARSE_SUCCESS') {
                    console.log("File parsed successfully.");
                    break;
                } else {
                    console.error(`Unknown file status: ${status}. Please contact technical support.`);
                    return null;
                }
                await this.sleep(5);
            }

            console.log("Step 7: Submitting a job to add documents to the index.");
            const indexAddResponse = await this.submitIndexAddDocumentsJob(client, workspaceId, indexId, fileId, sourceType);
            const jobId = indexAddResponse.body.data.id;

            console.log("Step 8: Waiting for the indexing job to complete.");
            while (true) {
                const getJobStatusResponse = await this.getIndexJobStatus(client, workspaceId, jobId, indexId);
                const status = getJobStatusResponse.body.data.status;
                console.log(`Current indexing job status: ${status}`);
                if (status === 'COMPLETED') {
                    break;
                }
                await this.sleep(5);
            }

            console.log("Step 9: Deleting the old document from the index.");
            await this.deleteIndexDocument(client, workspaceId, indexId, oldFileId);

            console.log("Knowledge base updated successfully.");
            return indexId;
        } catch (e) {
            console.error(`An error occurred: ${e.message}`);
            return null;
        }
    }

    /**
     * Waits for a specified number of seconds.
     * @param {number} seconds - The wait time in seconds.
     * @returns {Promise<void>}
     */
    static sleep(seconds) {
        return new Promise(resolve => setTimeout(resolve, seconds * 1000));
    }

    static async main(args) {
        if (!this.checkEnvironmentVariables()) {
            console.log("Environment variable check failed.");
            return;
        }

        const readline = require('readline').createInterface({
            input: process.stdin,
            output: process.stdout
        });

        try {
            const filePath = await new Promise((resolve, reject) => {
                readline.question("Enter the local path to the updated file (e.g., on Linux: /home/user/Alibaba_Cloud_Model_Studio_Phone_Series_Introduction.docx):", (ans) => {
                    ans.trim() ? resolve(ans) : reject(new Error("The path cannot be empty."));
                });
            });
            const indexId = await new Promise((resolve, reject) => {
                // The knowledge base ID is the Data.Id returned by the CreateIndex operation. You can also find this ID on the knowledge base page in the Model Studio console.
                readline.question("Enter the knowledge base ID to update:", (ans) => {
                    ans.trim() ? resolve(ans) : reject(new Error("The knowledge base ID cannot be empty."));
                });
            });
            const oldFileId = await new Promise((resolve, reject) => {
                // The file ID is the FileId returned by the AddFile operation. You can also find the file ID by clicking the ID icon next to the file name on the application data page in the Model Studio console.
                readline.question("Enter the ID of the file to replace:", (ans) => {
                    ans.trim() ? resolve(ans) : reject(new Error("The file ID cannot be empty."));
                });
            });
            const workspaceId = process.env.WORKSPACE_ID;

            const result = await this.updateKnowledgeBase(filePath, workspaceId, indexId, oldFileId);
            if (result) console.log(`Knowledge base ID: ${result}`);
            else console.log("Failed to update the knowledge base.");
        } catch (err) {
            console.error(err.message);
        } finally {
            readline.close();
        }
    }
}

exports.KbUpdate = KbUpdate;
KbUpdate.main(process.argv.slice(2));
```

## C#

```
// This sample code is for reference only. Do not use it in a production environment.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;

using Tea;
using Tea.Utils;

namespace AlibabaCloud.SDK.KnowledgeBase
{
    public class KnowledgeBaseUpdate
    {
        /// <summary>
        /// Checks if the required environment variables are set.
        /// </summary>
        /// <returns>Returns <see langword="true"/> if all required environment variables are set; otherwise, <see langword="false"/>.</returns>
        public static bool CheckEnvironmentVariables()
        {
            var requiredVars = new Dictionary<string, string>
            {
                { "ALIBABA_CLOUD_ACCESS_KEY_ID", "Alibaba Cloud AccessKey ID" },
                { "ALIBABA_CLOUD_ACCESS_KEY_SECRET", "Alibaba Cloud AccessKey Secret" },
                { "WORKSPACE_ID", "Alibaba Cloud Model Studio workspace ID" }
            };

            var missingVars = new List<string>();
            foreach (var entry in requiredVars)
            {
                string value = Environment.GetEnvironmentVariable(entry.Key);
                if (string.IsNullOrEmpty(value))
                {
                    missingVars.Add(entry.Key);
                    Console.WriteLine($"Error: Please set the {entry.Key} ({entry.Value}) environment variable.");
                }
            }

            return missingVars.Count == 0;
        }

        /// <summary>
        /// Calculates the MD5 hash of a file.
        /// </summary>
        /// <param name="filePath">The local path of the file.</param>
        /// <returns>The MD5 hash of the file.</returns>
        /// <exception cref="Exception">Thrown when an error occurs during calculation.</exception>
        public static string CalculateMD5(string filePath)
        {
            using (var md5 = MD5.Create())
            {
                using (var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read))
                {
                    byte[] hashBytes = md5.ComputeHash(stream);
                    StringBuilder sb = new StringBuilder();
                    foreach (byte b in hashBytes)
                    {
                        sb.Append(b.ToString("x2"));
                    }
                    return sb.ToString();
                }
            }
        }

        /// <summary>
        /// Gets the size of a file in bytes.
        /// </summary>
        /// <param name="filePath">The local path of the file.</param>
        /// <returns>The file size in bytes.</returns>
        public static string GetFileSize(string filePath)
        {
            var file = new FileInfo(filePath);
            return file.Length.ToString();
        }

        /// <summary>
        /// Initializes the client.
        /// </summary>
        /// <returns>A configured client object.</returns>
        /// <exception cref="Exception">Thrown when an error occurs during initialization.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Client CreateClient()
        {
            var config = new AlibabaCloud.OpenApiClient.Models.Config
            {
                AccessKeyId = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_ID"),
                AccessKeySecret = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            };
            // The endpoint below is the public endpoint for the China (Beijing) region. You can change it as needed.
            config.Endpoint = "bailian.cn-beijing.aliyuncs.com";
            return new AlibabaCloud.SDK.Bailian20231229.Client(config);
        }

        /// <summary>
        /// Requests a file upload lease.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="categoryId">The category ID.</param>
        /// <param name="fileName">The name of the file.</param>
        /// <param name="fileMd5">The MD5 hash of the file.</param>
        /// <param name="fileSize">The file size in bytes.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <returns>The response from the service.</returns>
        /// <exception cref="Exception">Thrown when an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.ApplyFileUploadLeaseResponse ApplyLease(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string categoryId,
            string fileName,
            string fileMd5,
            string fileSize,
            string workspaceId)
        {
            var headers = new Dictionary<string, string>() { };
            var applyFileUploadLeaseRequest = new AlibabaCloud.SDK.Bailian20231229.Models.ApplyFileUploadLeaseRequest
            {
                FileName = fileName,
                Md5 = fileMd5,
                SizeInBytes = fileSize
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.ApplyFileUploadLeaseWithOptions(categoryId, workspaceId, applyFileUploadLeaseRequest, headers, runtime);
        }

        /// <summary>
        /// Uploads a file to temporary storage.
        /// </summary>
        /// <param name="preSignedUrl">The pre-signed URL from the upload lease.</param>
        /// <param name="headers">The request headers for the upload.</param>
        /// <param name="filePath">The local path of the file.</param>
        /// <exception cref="Exception">Thrown when an error occurs during the upload.</exception>
        public static void UploadFile(string preSignedUrl, Dictionary<string, string> headers, string filePath)
        {
            var file = new FileInfo(filePath);
            if (!File.Exists(filePath))
            {
                throw new ArgumentException($"File does not exist or is not a regular file: {filePath}");
            }

            using (var fs = new FileStream(filePath, FileMode.Open, FileAccess.Read))
            {
                var url = new Uri(preSignedUrl);
                var conn = (HttpWebRequest)WebRequest.Create(url);
                conn.Method = "PUT";
                conn.ContentType = headers["Content-Type"];
                conn.Headers.Add("X-bailian-extra", headers["X-bailian-extra"]);

                byte[] buffer = new byte[4096];
                int bytesRead;
                while ((bytesRead = fs.Read(buffer, 0, buffer.Length)) > 0)
                {
                    conn.GetRequestStream().Write(buffer, 0, bytesRead);
                }

                using (var response = (HttpWebResponse)conn.GetResponse())
                {
                    if (response.StatusCode != HttpStatusCode.OK)
                    {
                        throw new Exception($"Upload failed with status code: {response.StatusCode}");
                    }
                }
            }
        }

        /// <summary>
        /// Adds a file to a category.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="leaseId">The lease ID.</param>
        /// <param name="parser">The parser to use for the file.</param>
        /// <param name="categoryId">The category ID.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <returns>The response from the service.</returns>
        /// <exception cref="Exception">Thrown when an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.AddFileResponse AddFile(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string leaseId,
            string parser,
            string categoryId,
            string workspaceId)
        {
            var headers = new Dictionary<string, string>() { };
            var addFileRequest = new AlibabaCloud.SDK.Bailian20231229.Models.AddFileRequest
            {
                LeaseId = leaseId,
                Parser = parser,
                CategoryId = categoryId
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.AddFileWithOptions(workspaceId, addFileRequest, headers, runtime);
        }

        /// <summary>
        /// Gets the basic information of a file.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="fileId">The file ID.</param>
        /// <returns>The response from the service.</returns>
        /// <exception cref="Exception">Thrown when an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.DescribeFileResponse DescribeFile(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string workspaceId,
            string fileId)
        {
            var headers = new Dictionary<string, string>() { };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.DescribeFileWithOptions(workspaceId, fileId, headers, runtime);
        }

        /// <summary>
        /// Appends a parsed file to a document-retrieval knowledge base.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="indexId">The index ID.</param>
        /// <param name="fileId">The file ID.</param>
        /// <param name="sourceType">The source type of the data.</param>
        /// <returns>The response from the service.</returns>
        public static AlibabaCloud.SDK.Bailian20231229.Models.SubmitIndexAddDocumentsJobResponse SubmitIndexAddDocumentsJob(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string workspaceId,
            string indexId,
            string fileId,
            string sourceType)
        {
            var headers = new Dictionary<string, string>() { };
            var submitIndexAddDocumentsJobRequest = new AlibabaCloud.SDK.Bailian20231229.Models.SubmitIndexAddDocumentsJobRequest
            {
                IndexId = indexId,
                DocumentIds = new List<string> { fileId },
                SourceType = sourceType
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.SubmitIndexAddDocumentsJobWithOptions(workspaceId, submitIndexAddDocumentsJobRequest, headers, runtime);
        }

        /// <summary>
        /// Queries the status of an index job.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="jobId">The job ID.</param>
        /// <param name="indexId">The index ID.</param>
        /// <returns>The response from the service.</returns>
        /// <exception cref="Exception">Thrown when an error occurs during the API call.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Models.GetIndexJobStatusResponse GetIndexJobStatus(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string workspaceId,
            string jobId,
            string indexId)
        {
            var headers = new Dictionary<string, string>() { };
            var getIndexJobStatusRequest = new AlibabaCloud.SDK.Bailian20231229.Models.GetIndexJobStatusRequest
            {
                IndexId = indexId,
                JobId = jobId
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.GetIndexJobStatusWithOptions(workspaceId, getIndexJobStatusRequest, headers, runtime);
        }

        /// <summary>
        /// Deletes one or more documents from a knowledge base index.
        /// </summary>
        /// <param name="client">The client object.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="indexId">The index ID.</param>
        /// <param name="fileId">The file ID.</param>
        /// <returns>The response from the service.</returns>
        public static AlibabaCloud.SDK.Bailian20231229.Models.DeleteIndexDocumentResponse DeleteIndexDocument(
            AlibabaCloud.SDK.Bailian20231229.Client client,
            string workspaceId,
            string indexId,
            string fileId)
        {
            var headers = new Dictionary<string, string>() { };
            var deleteIndexDocumentRequest = new AlibabaCloud.SDK.Bailian20231229.Models.DeleteIndexDocumentRequest
            {
                IndexId = indexId,
                DocumentIds = new List<string> { fileId }
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.DeleteIndexDocumentWithOptions(workspaceId, deleteIndexDocumentRequest, headers, runtime);
        }

        /// <summary>
        /// Updates a knowledge base.
        /// </summary>
        /// <param name="filePath">The local path of the updated file.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="indexId">The ID of the index to update.</param>
        /// <param name="oldFileId">The file ID of the file to be replaced.</param>
        /// <returns>The ID of the index if successful; otherwise, <see langword="null"/>.</returns>
        public static string UpdateKnowledgeBase(string filePath, string workspaceId, string indexId, string oldFileId)
        {
            // Set default values.
            string categoryId = "default";
            string parser = "DASHSCOPE_DOCMIND";
            string sourceType = "DATA_CENTER_FILE";

            try
            {
                Console.WriteLine("Step 1: Create a client.");
                var client = CreateClient();

                Console.WriteLine("Step 2: Prepare file information.");
                string fileName = Path.GetFileName(filePath);
                string fileMd5 = CalculateMD5(filePath);
                string fileSize = GetFileSize(filePath);

                Console.WriteLine("Step 3: Request an upload lease.");
                Bailian20231229.Models.ApplyFileUploadLeaseResponse leaseResponse = ApplyLease(client, categoryId, fileName, fileMd5, fileSize, workspaceId);
                string leaseId = leaseResponse.Body.Data.FileUploadLeaseId;
                string uploadUrl = leaseResponse.Body.Data.Param.Url;
                var uploadHeaders = leaseResponse.Body.Data.Param.Headers;

                Console.WriteLine("Step 4: Upload the file to temporary storage.");
                // Make sure the Newtonsoft.Json package is installed.
                var uploadHeadersMap = JsonConvert.DeserializeObject<Dictionary<string, string>>(JsonConvert.SerializeObject(uploadHeaders));
                UploadFile(uploadUrl, uploadHeadersMap, filePath);

                Console.WriteLine("Step 5: Add the file to the category.");
                Bailian20231229.Models.AddFileResponse addResponse = AddFile(client, leaseId, parser, categoryId, workspaceId);
                string fileId = addResponse.Body.Data.FileId;

                Console.WriteLine("Step 6: Check the file status.");
                while (true)
                {
                    Bailian20231229.Models.DescribeFileResponse describeResponse = DescribeFile(client, workspaceId, fileId);
                    string status = describeResponse.Body.Data.Status;
                    Console.WriteLine("Current file status: " + status);
                    if ("INIT".Equals(status))
                    {
                        Console.WriteLine("File is awaiting parsing. Please wait...");
                    }
                    else if ("PARSING".Equals(status))
                    {
                        Console.WriteLine("File parsing is in progress. Please wait...");
                    }
                    else if ("PARSE_SUCCESS".Equals(status))
                    {
                        Console.WriteLine("File parsing is complete!");
                        break;
                    }
                    else
                    {
                        Console.WriteLine("Unknown file status: " + status + ". Please contact technical support.");
                        return null;
                    }
                    System.Threading.Thread.Sleep(5000);
                }

                Console.WriteLine("Step 7: Submit a job to add the file to the index.");
                Bailian20231229.Models.SubmitIndexAddDocumentsJobResponse indexAddResponse = SubmitIndexAddDocumentsJob(client, workspaceId, indexId, fileId, sourceType);
                string jobId = indexAddResponse.Body.Data.Id;

                Console.WriteLine("Step 8: Wait for the indexing job to complete.");
                while (true)
                {
                    Bailian20231229.Models.GetIndexJobStatusResponse jobStatusResponse = GetIndexJobStatus(client, workspaceId, jobId, indexId);
                    string status = jobStatusResponse.Body.Data.Status;
                    Console.WriteLine("Current index job status: " + status);
                    if ("COMPLETED".Equals(status))
                    {
                        break;
                    }
                    System.Threading.Thread.Sleep(5000);
                }

                Console.WriteLine("Step 9: Delete the old file.");
                DeleteIndexDocument(client, workspaceId, indexId, oldFileId);

                Console.WriteLine("The knowledge base has been updated successfully!");
                return indexId;
            }
            catch (Exception e)
            {
                Console.WriteLine("An error occurred: " + e.Message);
                return null;
            }
        }

        /// <summary>
        /// The main entry point for the application.
        /// </summary>
        public static void Main(string[] args)
        {
            if (!CheckEnvironmentVariables())
            {
                Console.WriteLine("Environment variable validation failed.");
                return;
            }

            Console.Write("Enter the local path of the file to upload (e.g., /path/to/YourDocument.docx): ");
            string filePath = Console.ReadLine();

            Console.Write("Enter the ID of the knowledge base to update: "); // This is the `Data.Id` returned by the `CreateIndex` API call. Alternatively, you can find it on the knowledge bases page in the Alibaba Cloud Model Studio console.
            string indexId = Console.ReadLine();

            Console.Write("Enter the file ID of the file to be replaced: "); // This is the `FileId` returned by the `AddFile` API call. Alternatively, you can find it by clicking the ID icon next to a file name on the application data page in the Alibaba Cloud Model Studio console.
            string oldFileId = Console.ReadLine();

            string workspaceId = Environment.GetEnvironmentVariable("WORKSPACE_ID");
            string result = UpdateKnowledgeBase(filePath, workspaceId, indexId, oldFileId);
            if (result != null)
            {
                Console.WriteLine("The knowledge base has been updated successfully. Knowledge base ID: " + result);
            }
            else
            {
                Console.WriteLine("Failed to update the knowledge base.");
            }
        }
    }
}
```

## Go

```
// This sample code is for reference only. Do not use it in a production environment.
package main

import (
	"bufio"
	"crypto/md5"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	bailian20231229 "github.com/alibabacloud-go/bailian-20231229/v2/client"
	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	util "github.com/alibabacloud-go/tea-utils/v2/service"
	"github.com/alibabacloud-go/tea/tea"
	"github.com/go-resty/resty/v2"
)

// CheckEnvironmentVariables checks for and prompts you to set the required environment variables.
func CheckEnvironmentVariables() bool {
	// The required environment variables and their descriptions.
	requiredVars := map[string]string{
		"ALIBABA_CLOUD_ACCESS_KEY_ID":     "Alibaba Cloud AccessKey ID",
		"ALIBABA_CLOUD_ACCESS_KEY_SECRET": "Alibaba Cloud AccessKey Secret",
		"WORKSPACE_ID":                    "Alibaba Cloud Model Studio workspace ID",
	}

	var missingVars []string
	for varName, desc := range requiredVars {
		if os.Getenv(varName) == "" {
			fmt.Printf("Error: Set the %s environment variable (%s).\n", varName, desc)
			missingVars = append(missingVars, varName)
		}
	}

	return len(missingVars) == 0
}

// CalculateMD5 calculates the MD5 hash of a file.
//
// Parameters:
//   - filePath (string): The local path of the file.
//
// Returns:
//   - string: The MD5 hash of the file.
//   - error: The error message.
func CalculateMD5(filePath string) (_result string, _err error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	md5Hash := md5.New()
	_, err = io.Copy(md5Hash, file)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("%x", md5Hash.Sum(nil)), nil
}

// GetFileSize gets the size of a file in bytes.
//
// Parameters:
//   - filePath (string): The local path of the file.
//
// Returns:
//   - string: The file size in bytes.
//   - error: The error message.
func GetFileSize(filePath string) (_result string, _err error) {
	info, err := os.Stat(filePath)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%d", info.Size()), nil
}

// CreateClient creates and configures a client.
//
// Returns:
//   - *bailian20231229.Client: The configured client.
//   - error: The error message.
func CreateClient() (_result *bailian20231229.Client, _err error) {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	}
	// This example uses the public endpoint for the China (Beijing) region. You can change the endpoint as needed.
	config.Endpoint = tea.String("bailian.cn-beijing.aliyuncs.com")
	_result = &bailian20231229.Client{}
	_result, _err = bailian20231229.NewClient(config)
	return _result, _err
}

// ApplyLease requests a file upload lease from the Alibaba Cloud Model Studio service.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - categoryId (string): The category ID.
//   - fileName (string): The file name.
//   - fileMD5 (string): The MD5 hash of the file.
//   - fileSize (string): The file size in bytes.
//   - workspaceId (string): The workspace ID.
//
// Returns:
//   - *bailian20231229.ApplyFileUploadLeaseResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func ApplyLease(client *bailian20231229.Client, categoryId, fileName, fileMD5 string, fileSize string, workspaceId string) (_result *bailian20231229.ApplyFileUploadLeaseResponse, _err error) {
	headers := make(map[string]*string)
	applyFileUploadLeaseRequest := &bailian20231229.ApplyFileUploadLeaseRequest{
		FileName:    tea.String(fileName),
		Md5:         tea.String(fileMD5),
		SizeInBytes: tea.String(fileSize),
	}
	runtime := &util.RuntimeOptions{}
	return client.ApplyFileUploadLeaseWithOptions(tea.String(categoryId), tea.String(workspaceId), applyFileUploadLeaseRequest, headers, runtime)
}

// UploadFile uploads a file to the Alibaba Cloud Model Studio service.
//
// Parameters:
//   - preSignedUrl (string): The URL in the upload lease.
//   - headers (map[string]string): The request headers for the upload.
//   - filePath (string): The local path of the file.
func UploadFile(preSignedUrl string, headers map[string]string, filePath string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer file.Close()

	body, err := io.ReadAll(file)
	if err != nil {
		return err
	}

	client := resty.New()
	uploadHeaders := map[string]string{
		"X-bailian-extra": headers["X-bailian-extra"],
		"Content-Type":    headers["Content-Type"],
	}

	resp, err := client.R().
		SetHeaders(uploadHeaders).
		SetBody(body).
		Put(preSignedUrl)

	if err != nil {
		return err
	}

	if resp.IsError() {
		return fmt.Errorf("HTTP error: %d", resp.StatusCode())
	}

	return nil
}

// AddFile adds a file to a specified category in the Alibaba Cloud Model Studio service.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - leaseId (string): The lease ID.
//   - parser (string): The parser for the file.
//   - categoryId (string): The category ID.
//   - workspaceId (string): The workspace ID.
//
// Returns:
//   - *bailian20231229.AddFileResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func AddFile(client *bailian20231229.Client, leaseId, parser, categoryId, workspaceId string) (_result *bailian20231229.AddFileResponse, _err error) {
	headers := make(map[string]*string)
	addFileRequest := &bailian20231229.AddFileRequest{
		LeaseId:    tea.String(leaseId),
		Parser:     tea.String(parser),
		CategoryId: tea.String(categoryId),
	}
	runtime := &util.RuntimeOptions{}
	return client.AddFileWithOptions(tea.String(workspaceId), addFileRequest, headers, runtime)
}

// DescribeFile gets the basic information of a file.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - workspaceId (string): The workspace ID.
//   - fileId (string): The file ID.
//
// Returns:
//   - *bailian20231229.DescribeFileResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func DescribeFile(client *bailian20231229.Client, workspaceId, fileId string) (_result *bailian20231229.DescribeFileResponse, _err error) {
	headers := make(map[string]*string)
	runtime := &util.RuntimeOptions{}
	return client.DescribeFileWithOptions(tea.String(workspaceId), tea.String(fileId), headers, runtime)
}

// SubmitIndexAddDocumentsJob appends a parsed file to a knowledge base.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - workspaceId (string): The workspace ID.
//   - indexId (string): The knowledge base ID.
//   - fileId (string): The file ID.
//   - sourceType (string): The data type.
//
// Returns:
//   - *bailian20231229.SubmitIndexAddDocumentsJobResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func SubmitIndexAddDocumentsJob(client *bailian20231229.Client, workspaceId, indexId, fileId, sourceType string) (_result *bailian20231229.SubmitIndexAddDocumentsJobResponse, _err error) {
	headers := make(map[string]*string)
	submitIndexAddDocumentsJobRequest := &bailian20231229.SubmitIndexAddDocumentsJobRequest{
		IndexId:     tea.String(indexId),
		SourceType:  tea.String(sourceType),
		DocumentIds: []*string{tea.String(fileId)},
	}
	runtime := &util.RuntimeOptions{}
	return client.SubmitIndexAddDocumentsJobWithOptions(tea.String(workspaceId), submitIndexAddDocumentsJobRequest, headers, runtime)
}

// GetIndexJobStatus queries the status of an index job.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - workspaceId (string): The workspace ID.
//   - jobId (string): The job ID.
//   - indexId (string): The knowledge base ID.
//
// Returns:
//   - *bailian20231229.GetIndexJobStatusResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func GetIndexJobStatus(client *bailian20231229.Client, workspaceId, jobId, indexId string) (_result *bailian20231229.GetIndexJobStatusResponse, _err error) {
	headers := make(map[string]*string)
	getIndexJobStatusRequest := &bailian20231229.GetIndexJobStatusRequest{
		JobId:   tea.String(jobId),
		IndexId: tea.String(indexId),
	}
	runtime := &util.RuntimeOptions{}
	return client.GetIndexJobStatusWithOptions(tea.String(workspaceId), getIndexJobStatusRequest, headers, runtime)
}

// DeleteIndexDocument permanently deletes one or more files from a specified knowledge base.
//
// Parameters:
//   - client (*bailian20231229.Client): The client.
//   - workspaceId (string): The workspace ID.
//   - indexId (string): The knowledge base ID.
//   - fileId (string): The file ID.
//
// Returns:
//   - *bailian20231229.DeleteIndexDocumentResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: The error message.
func DeleteIndexDocument(client *bailian20231229.Client, workspaceId, indexId, fileId string) (*bailian20231229.DeleteIndexDocumentResponse, error) {
	headers := make(map[string]*string)
	deleteIndexDocumentRequest := &bailian20231229.DeleteIndexDocumentRequest{
		IndexId:     tea.String(indexId),
		DocumentIds: []*string{tea.String(fileId)},
	}
	runtime := &util.RuntimeOptions{}
	return client.DeleteIndexDocumentWithOptions(tea.String(workspaceId), deleteIndexDocumentRequest, headers, runtime)
}

// UpdateKnowledgeBase updates a knowledge base.
//
// Parameters:
//   - filePath (string): The local path of the updated file.
//   - workspaceId (string): The workspace ID.
//   - indexId (string): The ID of the knowledge base to update.
//   - oldFileId (string): The file ID of the file to update.
//
// Returns:
//   - string: The ID of the knowledge base if the update is successful, or an empty string otherwise.
//   - error: The error message.
func UpdateKnowledgeBase(filePath, workspaceId, indexId, oldFileId string) (_result string, _err error) {
	// Set default values.
	categoryId := "default"
	parser := "DASHSCOPE_DOCMIND"
	sourceType := "DATA_CENTER_FILE"

	fmt.Println("Step 1: Create a client.")
	client, err := CreateClient()
	if err != nil {
		return "", err
	}

	fmt.Println("Step 2: Prepare file information.")
	fileName := filepath.Base(filePath)
	fileMD5, err := CalculateMD5(filePath)
	if err != nil {
		return "", err
	}
	fileSizeStr, err := GetFileSize(filePath)
	if err != nil {
		return "", err
	}

	fmt.Println("Step 3: Request an upload lease from Alibaba Cloud Model Studio.")
	leaseResponse, err := ApplyLease(client, categoryId, fileName, fileMD5, fileSizeStr, workspaceId)
	if err != nil {
		return "", err
	}

	leaseId := tea.StringValue(leaseResponse.Body.Data.FileUploadLeaseId)
	uploadURL := tea.StringValue(leaseResponse.Body.Data.Param.Url)
	uploadHeaders := leaseResponse.Body.Data.Param.Headers

	jsonData, err := json.Marshal(uploadHeaders)
	if err != nil {
		return "", err
	}

	var uploadHeadersMap map[string]string
	err = json.Unmarshal(jsonData, &uploadHeadersMap)
	if err != nil {
		return "", err
	}

	fmt.Println("Step 4: Upload the file to temporary storage.")
	err = UploadFile(uploadURL, uploadHeadersMap, filePath)
	if err != nil {
		return "", err
	}

	fmt.Println("Step 5: Add the file to the category.")
	addResponse, err := AddFile(client, leaseId, parser, categoryId, workspaceId)
	if err != nil {
		return "", err
	}
	fileId := tea.StringValue(addResponse.Body.Data.FileId)

	fmt.Println("Step 6: Check the file status in Alibaba Cloud Model Studio.")
	for {
		describeResponse, err := DescribeFile(client, workspaceId, fileId)
		if err != nil {
			return "", err
		}

		status := tea.StringValue(describeResponse.Body.Data.Status)
		fmt.Printf("Current file status: %s\n", status)

		if status == "INIT" {
			fmt.Println("The file is pending parsing. Please wait...")
		} else if status == "PARSING" {
			fmt.Println("The file is being parsed. Please wait...")
		} else if status == "PARSE_SUCCESS" {
			fmt.Println("The file was parsed successfully.")
			break
		} else {
			fmt.Printf("Unknown file status: %s. Contact technical support.\n", status)
			return "", fmt.Errorf("unknown file status: %s", status)
		}
		time.Sleep(5 * time.Second)
	}

	// Submit a task to append the file.
	fmt.Println("Step 7: Submit a task to append the file.")
	indexAddResponse, err := SubmitIndexAddDocumentsJob(client, workspaceId, indexId, fileId, sourceType)
	if err != nil {
		return "", err
	}
	jobId := tea.StringValue(indexAddResponse.Body.Data.Id)

	// Wait for the task to complete.
	fmt.Println("Step 8: Wait for the append task to complete.")
	for {
		getIndexJobStatusResponse, err := GetIndexJobStatus(client, workspaceId, jobId, indexId)
		if err != nil {
			return "", err
		}

		status := tea.StringValue(getIndexJobStatusResponse.Body.Data.Status)
		fmt.Printf("Current index job status: %s\n", status)

		if status == "COMPLETED" {
			break
		}
		time.Sleep(5 * time.Second)
	}

	// Delete the old file.
	fmt.Println("Step 9: Delete the old file.")
	_, err = DeleteIndexDocument(client, workspaceId, indexId, oldFileId)
	if err != nil {
		return "", err
	}

	fmt.Println("The Alibaba Cloud Model Studio knowledge base was updated successfully.")
	return indexId, nil
}

func main() {
	if !CheckEnvironmentVariables() {
		fmt.Println("The environment variable check failed.")
		return
	}
	// Create a scanner to read input.
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("Enter the local path of the updated file to upload (for example, on a Linux system: /path/to/product_introduction.docx):")
	filePath, _ := reader.ReadString('\n')
	filePath = strings.TrimSpace(filePath)

	fmt.Print("Enter the ID of the knowledge base to update:") // This is the Data.Id returned by the CreateIndex operation. You can also obtain the ID on the knowledge base page in the Model Studio console.
	indexId, _ := reader.ReadString('\n')
	indexId = strings.TrimSpace(indexId)

	fmt.Print("Enter the file ID of the file to update:") // This is the FileId returned by the AddFile operation. You can also obtain the file ID by clicking the ID icon next to the file name on the application data page in the Model Studio console.
	oldFileId, _ := reader.ReadString('\n')
	oldFileId = strings.TrimSpace(oldFileId)

	workspaceId := os.Getenv("WORKSPACE_ID")
	result, err := UpdateKnowledgeBase(filePath, workspaceId, indexId, oldFileId)
	if err != nil {
		fmt.Printf("An error occurred: %v\n", err)
		return
	}

	if result != "" {
		fmt.Printf("The knowledge base was updated successfully. The knowledge base ID is: %s\n", result)
	} else {
		fmt.Println("Failed to update the knowledge base.")
	}
}
```

## Manage knowledge bases

**Important**

-   Before running this example, complete the [prerequisites](#a4a15bd543can). RAM users must also be [granted the AliyunBailianDataFullAccess policy](https://help.aliyun.com/en/model-studio/grant-data-access-permission-to-ram-user).
    
-   If you use an IDE or other development plugins, set the `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, and `WORKSPACE_ID` environment variables in your development environment.
    

## Python

```
# This sample code is for reference only. Do not use it in a production environment.
import os

from alibabacloud_bailian20231229 import models as bailian_20231229_models
from alibabacloud_bailian20231229.client import Client as bailian20231229Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient


def check_environment_variables():
    """Verifies that the required environment variables are set."""
    required_vars = {
        'ALIBABA_CLOUD_ACCESS_KEY_ID': 'Alibaba Cloud AccessKey ID',
        'ALIBABA_CLOUD_ACCESS_KEY_SECRET': 'Alibaba Cloud AccessKey secret',
        'WORKSPACE_ID': 'Alibaba Cloud Model Studio workspace ID'
    }
    missing_vars = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing_vars.append(var)
            print(f"Error: Please set the {var} environment variable ({description})")

    return len(missing_vars) == 0


# Create a client.
def create_client() -> bailian20231229Client:
    """
    Creates and configures a client.

    Returns:
        bailian20231229Client: The configured client.
    """
    config = open_api_models.Config(
        access_key_id=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID'),
        access_key_secret=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    )
    # The following endpoint is for the public cloud in the China (Beijing) region. Change it as needed.
    config.endpoint = 'bailian.cn-beijing.aliyuncs.com'
    return bailian20231229Client(config)


# List knowledge bases.
def list_indices(client, workspace_id):
    """
    Lists the knowledge bases in a specified workspace.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.

    Returns:
        The response from the Alibaba Cloud Model Studio service.
    """
    headers = {}
    list_indices_request = bailian_20231229_models.ListIndicesRequest()
    runtime = util_models.RuntimeOptions()
    return client.list_indices_with_options(workspace_id, list_indices_request, headers, runtime)


# Delete a knowledge base.
def delete_index(client, workspace_id, index_id):
    """
    Permanently deletes the specified knowledge base.

    Args:
        client (bailian20231229Client): The client.
        workspace_id (str): The workspace ID.
        index_id (str): The knowledge base ID.

    Returns:
        The response from the Alibaba Cloud Model Studio service.
    """
    headers = {}
    delete_index_request = bailian_20231229_models.DeleteIndexRequest(
        index_id=index_id
    )
    runtime = util_models.RuntimeOptions()
    return client.delete_index_with_options(workspace_id, delete_index_request, headers, runtime)


def main():
    if not check_environment_variables():
        print("Environment variable check failed.")
        return
    try:
        start_option = input(
            "Select an operation to perform:\n1. List knowledge bases\n2. Delete a knowledge base\nEnter an option (1 or 2):")
        if start_option == '1':
            # List knowledge bases.
            print("\nListing knowledge bases...")
            workspace_id = os.environ.get('WORKSPACE_ID')
            client = create_client()
            list_indices_response = list_indices(client, workspace_id)
            print(UtilClient.to_jsonstring(list_indices_response.body.data))
        elif start_option == '2':
            print("\nDeleting a knowledge base...")
            workspace_id = os.environ.get('WORKSPACE_ID')
            index_id = input("Enter the knowledge base ID: ")  # This is the `Data.Id` value from the `CreateIndex` response. You can also find it on the knowledge base page in the Model Studio console.
            # Confirm before deletion.
            while True:
                confirm = input(f"Are you sure you want to permanently delete the knowledge base {index_id}? (y/n): ").strip().lower()
                if confirm == 'y':
                    break
                elif confirm == 'n':
                    print("Deletion canceled.")
                    return
                else:
                    print("Invalid input. Please enter y or n.")
            client = create_client()
            resp = delete_index(client, workspace_id, index_id)
            if resp.body.status == 200:
                print(f"Knowledge base {index_id} deleted successfully.")
            else:
                err_info = UtilClient.to_jsonstring(resp.body)
                print(f"An error occurred: {err_info}")
        else:
            print("Invalid option. Exiting program.")
            return
    except Exception as e:
        print(f"An error occurred: {e}")
        return


if __name__ == '__main__':
    main()
```

## Java

```
// This sample code is for reference only. Do not use it in a production environment.
import com.aliyun.bailian20231229.models.DeleteIndexResponse;
import com.aliyun.bailian20231229.models.ListIndicesResponse;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.*;

public class KnowledgeBaseManage {

    /**
     * Verifies that the required environment variables are set.
     *
     * @return true if all required environment variables are set, false otherwise.
     */
    public static boolean checkEnvironmentVariables() {
        Map<String, String> requiredVars = new HashMap<>();
        requiredVars.put("ALIBABA_CLOUD_ACCESS_KEY_ID", "Alibaba Cloud AccessKey ID");
        requiredVars.put("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "Alibaba Cloud AccessKey secret");
        requiredVars.put("WORKSPACE_ID", "Alibaba Cloud Model Studio workspace ID");

        List<String> missingVars = new ArrayList<>();
        for (Map.Entry<String, String> entry : requiredVars.entrySet()) {
            String value = System.getenv(entry.getKey());
            if (value == null || value.isEmpty()) {
                missingVars.add(entry.getKey());
                System.out.println("Error: Please set the " + entry.getKey() + " environment variable (" + entry.getValue() + ")");
            }
        }

        return missingVars.isEmpty();
    }

    /**
     * Creates and configures a client.
     *
     * @return The configured client.
     */
    public static com.aliyun.bailian20231229.Client createClient() throws Exception {
        com.aliyun.credentials.Client credential = new com.aliyun.credentials.Client();
        com.aliyun.teaopenapi.models.Config config = new com.aliyun.teaopenapi.models.Config()
                .setCredential(credential);
        // This is a public cloud endpoint. Change it to match your region.
        config.endpoint = "bailian.cn-beijing.aliyuncs.com";
        return new com.aliyun.bailian20231229.Client(config);
    }

    /**
     * Lists the knowledge bases in a specified workspace.
     *
     * @param client      The client.
     * @param workspaceId The workspace ID.
     * @return The response from the Model Studio service.
     */
    public static ListIndicesResponse listIndices(com.aliyun.bailian20231229.Client client, String workspaceId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.ListIndicesRequest listIndicesRequest = new com.aliyun.bailian20231229.models.ListIndicesRequest();
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        return client.listIndicesWithOptions(workspaceId, listIndicesRequest, headers, runtime);
    }

    /**
     * Permanently deletes the specified knowledge base.
     *
     * @param client      The client.
     * @param workspaceId The workspace ID.
     * @param indexId     The knowledge base ID.
     * @return The response from the Model Studio service.
     */
    public static DeleteIndexResponse deleteIndex(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId) throws Exception {
        Map<String, String> headers = new HashMap<>();
        com.aliyun.bailian20231229.models.DeleteIndexRequest deleteIndexRequest = new com.aliyun.bailian20231229.models.DeleteIndexRequest();
        deleteIndexRequest.setIndexId(indexId);
        com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions();
        return client.deleteIndexWithOptions(workspaceId, deleteIndexRequest, headers, runtime);
    }

    /**
     * The main function.
     */
    public static void main(String[] args) {
        if (!checkEnvironmentVariables()) {
            System.out.println("Environment variable check failed.");
            return;
        }

        try {
            Scanner scanner = new Scanner(System.in);
            System.out.print("Select an operation to perform:\n1. List knowledge bases\n2. Delete a knowledge base\nEnter an option (1 or 2): ");
            String startOption = scanner.nextLine();
            com.aliyun.bailian20231229.Client client = createClient();
            if (startOption.equals("1")) {
                // List knowledge bases
                System.out.println("\nListing knowledge bases...");
                String workspaceId = System.getenv("WORKSPACE_ID");
                ListIndicesResponse response = listIndices(client, workspaceId);
                // Requires the jackson-databind library to convert the response to a JSON string.
                ObjectMapper mapper = new ObjectMapper();
                String result = mapper.writeValueAsString(response.getBody().getData());
                System.out.println(result);
            } else if (startOption.equals("2")) {
                System.out.println("\nDeleting a knowledge base...");
                String workspaceId = System.getenv("WORKSPACE_ID");
                System.out.print("Enter the knowledge base ID: "); // This ID is the Data.Id value returned by the CreateIndex operation. You can also find it on the knowledge base page in the Model Studio console.
                String indexId = scanner.nextLine();
                // Prompt for confirmation before deletion.
                boolean confirm = false;
                while (!confirm) {
                    System.out.print("Are you sure you want to permanently delete knowledge base " + indexId + "? (y/n): ");
                    String input = scanner.nextLine().trim().toLowerCase();
                    if (input.equals("y")) {
                        confirm = true;
                    } else if (input.equals("n")) {
                        System.out.println("Deletion canceled.");
                        return;
                    } else {
                        System.out.println("Invalid input. Please enter y or n.");
                    }
                }
                DeleteIndexResponse resp = deleteIndex(client, workspaceId, indexId);
                if (resp.getBody().getStatus().equals("200")) {
                    System.out.println("Knowledge base " + indexId + " deleted successfully.");
                } else {
                    ObjectMapper mapper = new ObjectMapper();
                    System.out.println("An error occurred: " + mapper.writeValueAsString(resp.getBody()));
                }
            } else {
                System.out.println("Invalid option. Exiting program.");
            }
        } catch (Exception e) {
            System.out.println("An error occurred: " + e.getMessage());
        }
    }
}
```

## PHP

```
<?php
// This sample code is for reference only. Do not use it in a production environment.
namespace AlibabaCloud\SDK\Sample;

use AlibabaCloud\Dara\Models\RuntimeOptions;
use AlibabaCloud\SDK\Bailian\V20231229\Bailian;
use AlibabaCloud\SDK\Bailian\V20231229\Models\DeleteIndexRequest;
use AlibabaCloud\SDK\Bailian\V20231229\Models\ListIndexDocumentsRequest;
use \Exception;

use Darabonba\OpenApi\Models\Config;

class KnowledgeBaseManage {

    /**
    * Verifies that the required environment variables are set.
    *
    * @return bool Returns true if all required environment variables are set, false otherwise.
    */
    public static function checkEnvironmentVariables() {
        $requiredVars = [
            'ALIBABA_CLOUD_ACCESS_KEY_ID' => 'Alibaba Cloud AccessKey ID',
            'ALIBABA_CLOUD_ACCESS_KEY_SECRET' => 'Alibaba Cloud AccessKey secret',
            'WORKSPACE_ID' => 'Alibaba Cloud Model Studio workspace ID'
        ];
        $missingVars = [];
        foreach ($requiredVars as $var => $description) {
            if (!getenv($var)) {
                $missingVars[] = $var;
                echo "Error: Set the $var environment variable ($description)\n";
            }
        }
        return count($missingVars) === 0;
    }

    /**
     * Initializes the client.
     *
     * @return Bailian The configured client object.
     */
    public static function createClient(){
        $config = new Config([
            "accessKeyId" => getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"), 
            "accessKeySecret" => getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        ]);
        // This is a public cloud endpoint. Change it if necessary.
        $config->endpoint = 'bailian.cn-beijing.aliyuncs.com';
        return new Bailian($config);
    }

     /**
     * Lists the knowledge bases in a specified workspace.
     *
     * @param Bailian $client The client object.
     * @param string $workspaceId The workspace ID.
     * @return ListIndicesResponse The response from the Model Studio service.
     * @throws Exception
     */
    public static function listIndices($client, $workspaceId) {
        $headers = [];
        $listIndexDocumentsRequest = new ListIndexDocumentsRequest([]);
        $runtime = new RuntimeOptions([]);
        return $client->listIndicesWithOptions($workspaceId, $listIndexDocumentsRequest, $headers, $runtime);
    }

    /**
     * Permanently deletes the specified knowledge base.
     *
     * @param Bailian $client The client object.
     * @param string $workspaceId The workspace ID.
     * @param string $indexId The knowledge base ID.
     * @return mixed The response from the Model Studio service.
     * @throws Exception
     */
    public static function deleteIndex($client, $workspaceId, $indexId) {
        $headers = [];
        $deleteIndexRequest = new DeleteIndexRequest([
            "indexId" => $indexId
        ]);
        $runtime = new RuntimeOptions([]);
        return $client->deleteIndexWithOptions($workspaceId, $deleteIndexRequest, $headers, $runtime);
    }

    /**
     * The main function.
     */
    public static function main($args) {
        if (!self::checkEnvironmentVariables()) {
            echo "The environment variable check failed.\n";
            return;
        }

        try {
            echo "Select an operation to perform:\n1. List knowledge bases\n2. Delete a knowledge base\nEnter an option (1 or 2):";
            $startOption = trim(fgets(STDIN));
            $client = self::createClient();
            if ($startOption === "1") {
                // List knowledge bases.
                echo "\nList knowledge bases\n";
                $workspaceId = getenv("WORKSPACE_ID");
                $response = self::listIndices($client, $workspaceId);
                // Convert the response to a JSON string.
                $result = json_encode($response->body->data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
                echo $result . "\n";
            } elseif ($startOption === "2") {
                echo "\nDelete a knowledge base\n";
                $workspaceId = getenv("WORKSPACE_ID");
                $indexId = readline("Enter the knowledge base ID:"); // The ID is returned as `Data.Id` by the CreateIndex operation. You can also find it on the knowledge base page in the Model Studio console.
                // Confirm before deletion.
                while (true) {
                    $confirm = strtolower(trim(readline("Are you sure you want to permanently delete the knowledge base $indexId? (y/n): ")));
                    if ($confirm === 'y') {
                        break;
                    } elseif ($confirm === 'n') {
                        echo "Deletion canceled.\n";
                        return;
                    } else {
                        echo "Invalid input. Enter y or n.\n";
                    }
                }
                $response = self::deleteIndex($client, $workspaceId, $indexId);
                if ($response->body->status == "200")
                    echo "Knowledge base " . $indexId . " has been deleted.\n";
                else 
                    echo "An error occurred: " . json_encode($response->body) . "\n";
            } else {
                echo "Invalid option. Exiting.\n";
            }
        } catch (Exception $e) {
            echo "An error occurred: " . $e->getMessage() . "\n";
        }
    }
}
// Assumes autoload.php is in the parent directory of this file. Adjust the path according to your project structure.
$path = __DIR__ . \DIRECTORY_SEPARATOR . '..' . \DIRECTORY_SEPARATOR . 'vendor' . \DIRECTORY_SEPARATOR . 'autoload.php';
if (file_exists($path)) {
    require_once $path;
}
KnowledgeBaseManage::main(array_slice($argv, 1));
```

## Node.js

```
// This sample code is for reference only. Do not use it in a production environment.
'use strict';

const bailian20231229 = require('@alicloud/bailian20231229');
const OpenApi = require('@alicloud/openapi-client');
const Util = require('@alicloud/tea-util');
const Tea = require('@alicloud/tea-typescript');

class KbManage {

    /**
     * Verifies that required environment variables are set.
     * @returns {boolean} True if all required environment variables are set, false otherwise.
     */
    static checkEnvironmentVariables() {
        const requiredVars = {
            'ALIBABA_CLOUD_ACCESS_KEY_ID': 'Alibaba Cloud access key ID',
            'ALIBABA_CLOUD_ACCESS_KEY_SECRET': 'Alibaba Cloud access key secret',
            'WORKSPACE_ID': 'Alibaba Cloud Model Studio workspace ID'
        };

        const missing = [];
        for (const [varName, desc] of Object.entries(requiredVars)) {
            if (!process.env[varName]) {
                console.error(`Error: Set the ${varName} environment variable (${desc})`);
                missing.push(varName);
            }
        }

        return missing.length === 0;
    }

    /**
     * Creates and configures a client.
     * @returns {bailian20231229.default} The configured client.
     * @throws {Error} Throws an error if credentials are not configured.
     */
    static createClient() {
        const config = new OpenApi.Config({
            accessKeyId: process.env.ALIBABA_CLOUD_ACCESS_KEY_ID,
            accessKeySecret: process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET
        });
        // The following endpoint is for the public cloud. You can change the endpoint as needed.
        config.endpoint = 'bailian.cn-beijing.aliyuncs.com';
        return new bailian20231229.default(config);
    }

    /**
     * Lists the knowledge bases in a specified workspace.
     * @param {bailian20231229.Client} client The client instance to use for the request.
     * @param {string} workspaceId The ID of the workspace to query.
     * @returns {Promise<bailian20231229.ListIndicesResponse>} A promise that resolves with the service response.
     */
    static async listIndices(client, workspaceId) {
        const headers = {};
        const listIndicesRequest = new bailian20231229.ListIndicesRequest();
        const runtime = new Util.RuntimeOptions({});
        return await client.listIndicesWithOptions(workspaceId, listIndicesRequest, headers, runtime);
    }

    /**
     * Permanently deletes the specified knowledge base.
     * @param {bailian20231229.Client} client The client instance to use for the request.
     * @param {string} workspaceId The ID of the workspace containing the knowledge base.
     * @param {string} indexId The ID of the knowledge base to delete.
     * @returns {Promise<bailian20231229.DeleteIndexResponse>} A promise that resolves with the service response.
     */
    static async deleteIndex(client, workspaceId, indexId) {
        const headers = {};
        const deleteIndexRequest = new bailian20231229.DeleteIndexRequest({
            indexId
        });
        const runtime = new Util.RuntimeOptions({});
        return await client.deleteIndexWithOptions(workspaceId, deleteIndexRequest, headers, runtime);
    }

    /**
     * Provides a command-line interface to list or delete knowledge bases.
     */
    static async main(args) {
        if (!this.checkEnvironmentVariables()) {
            console.log("Environment variable check failed.");
            return;
        }

        const readline = require('readline').createInterface({
            input: process.stdin,
            output: process.stdout
        });

        try {
            const startOption = await new Promise((resolve) => {
                readline.question("Select an operation to perform:\n1. List knowledge bases\n2. Delete a knowledge base\nEnter an option (1 or 2):", (ans) => {
                    resolve(ans.trim());
                });
            });

            if (startOption === '1') {
                console.log("\nListing knowledge bases...");
                const workspaceId = process.env.WORKSPACE_ID;
                const client = this.createClient();
                const response = await this.listIndices(client, workspaceId);
                console.log(JSON.stringify(response.body.data));
            } else if (startOption === '2') {
                console.log("\nDeleting a knowledge base...");
                const workspaceId = process.env.WORKSPACE_ID;
                const indexId = await new Promise((resolve) => {
                    readline.question("Enter the knowledge base ID: ", (ans) => { // This ID corresponds to the `Data.Id` value from the `CreateIndex` API response. You can also find it on the knowledge base page in the Model Studio console.
                        resolve(ans.trim());
                    });
                });
                // Confirm before deletion.
                let confirm = '';
                while (confirm !== 'y' && confirm !== 'n') {
                    confirm = (await new Promise((resolve) => {
                        readline.question(`Are you sure you want to permanently delete the knowledge base ${indexId}? (y/n): `, (ans) => {
                            resolve(ans.trim().toLowerCase());
                        });
                    })).toLowerCase();
                    if (confirm === 'n') {
                        console.log("Deletion canceled.");
                        return;
                    } else if (confirm !== 'y') {
                        console.log("Invalid input. Please enter y or n.");
                    }
                }
                const client = this.createClient();
                const resp = await this.deleteIndex(client, workspaceId, indexId);
                if (resp.body.status == '200')
                    console.log(`Knowledge base ${indexId} deleted successfully.`);
                else {
                    const errInfo = JSON.stringify(resp.body);
                    console.error(`An error occurred: ${errInfo}`)
                }
            } else {
                console.log("Invalid option. Exiting.");
            }
        } catch (err) {
            console.error(`An error occurred: ${err.message}`);
        } finally {
            readline.close();
        }
    }
}

exports.KbManage = KbManage;
KbManage.main(process.argv.slice(2));
```

## C#

```
// This sample code is for reference only. Do not use it in a production environment.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;

using Newtonsoft.Json;
using Tea;
using Tea.Utils;


namespace AlibabaCloud.SDK.KnowledgeBase
{
    public class KnowledgeBaseManage
    {
        /// <summary>
        /// Checks for required environment variables and prompts for missing ones.
        /// </summary>
        /// <returns>`true` if all required environment variables are set; otherwise, `false`.</returns>
        public static bool CheckEnvironmentVariables()
        {
            var requiredVars = new Dictionary<string, string>
            {
                { "ALIBABA_CLOUD_ACCESS_KEY_ID", "Alibaba Cloud AccessKey ID" },
                { "ALIBABA_CLOUD_ACCESS_KEY_SECRET", "Alibaba Cloud AccessKey secret" },
                { "WORKSPACE_ID", "Alibaba Cloud Model Studio workspace ID" }
            };

            var missingVars = new List<string>();
            foreach (var entry in requiredVars)
            {
                string value = Environment.GetEnvironmentVariable(entry.Key);
                if (string.IsNullOrEmpty(value))
                {
                    missingVars.Add(entry.Key);
                    Console.WriteLine($"Error: Please set the {entry.Key} environment variable ({entry.Value})");
                }
            }

            return missingVars.Count == 0;
        }

        /// <summary>
        /// Initializes a client.
        /// </summary>
        /// <returns>The configured client object.</returns>
        /// <exception cref="Exception">An exception is thrown if an error occurs during initialization.</exception>
        public static AlibabaCloud.SDK.Bailian20231229.Client CreateClient()
        {
            var config = new AlibabaCloud.OpenApiClient.Models.Config
            {
                AccessKeyId = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_ID"),
                AccessKeySecret = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            };
            // The following is an example public endpoint. You can change it as needed.
            config.Endpoint = "bailian.cn-beijing.aliyuncs.com";
            return new AlibabaCloud.SDK.Bailian20231229.Client(config);
        }

        /// <summary>
        /// Gets the details of knowledge bases in a specified workspace.
        /// </summary>
        /// <param name="client">The client.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <returns>The response from the Model Studio service.</returns>
        public static AlibabaCloud.SDK.Bailian20231229.Models.ListIndicesResponse ListIndices(AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId)
        {
            var headers = new Dictionary<string, string>() { };
            var listIndicesRequest = new Bailian20231229.Models.ListIndicesRequest();
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.ListIndicesWithOptions(workspaceId, listIndicesRequest, headers, runtime);
        }

        /// <summary>
        /// Permanently deletes the specified knowledge base.
        /// </summary>
        /// <param name="client">The client.</param>
        /// <param name="workspaceId">The workspace ID.</param>
        /// <param name="indexId">The knowledge base ID.</param>
        /// <returns>The response from the Model Studio service.</returns>
        public static AlibabaCloud.SDK.Bailian20231229.Models.DeleteIndexResponse DeleteIndex(AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string indexId)
        {
            var headers = new Dictionary<string, string>() { };
            var deleteIndexRequest = new Bailian20231229.Models.DeleteIndexRequest
            {
                IndexId = indexId
            };
            var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions();
            return client.DeleteIndexWithOptions(workspaceId, deleteIndexRequest, headers, runtime);
        }

        /// <summary>
        /// The main function.
        /// </summary>
        public static void Main(string[] args)
        {
            if (!CheckEnvironmentVariables())
            {
                Console.WriteLine("Environment variable check failed.");
                return;
            }
            try
            {
                Console.Write("Select an operation to perform:\n1. List knowledge bases\n2. Delete a knowledge base\nPlease enter an option (1 or 2):");
                string startOption = Console.ReadLine();
                if (startOption == "1")
                {
                    Console.WriteLine("\nListing knowledge bases...");
                    string workspaceId = Environment.GetEnvironmentVariable("WORKSPACE_ID");
                    Bailian20231229.Client client = CreateClient();
                    Bailian20231229.Models.ListIndicesResponse listIndicesResponse = ListIndices(client, workspaceId);
                    // Install Newtonsoft.Json to serialize the response object to a JSON string.
                    var json = JsonConvert.SerializeObject(listIndicesResponse.Body.Data, Formatting.Indented);
                    Console.WriteLine(json);
                }
                else if (startOption == "2")
                {
                    Console.WriteLine("\nDeleting a knowledge base...");
                    string workspaceId = Environment.GetEnvironmentVariable("WORKSPACE_ID");
                    Console.Write("Please enter the knowledge base ID: "); // The knowledge base ID (Data.Id) is returned by the CreateIndex operation or can be found on the knowledge base page in the Model Studio console.
                    string indexId = Console.ReadLine();
                    // Confirm before deletion.
                    while (true)
                    {
                        Console.Write($"Are you sure you want to permanently delete the knowledge base {indexId}? (y/n): ");
                        string confirm = Console.ReadLine()?.ToLower();
                        if (confirm == "y")
                        {
                            break;
                        }
                        else if (confirm == "n")
                        {
                            Console.WriteLine("Deletion canceled.");
                            return;
                        }
                        else
                        {
                            Console.WriteLine("Invalid input. Please enter y or n.");
                        }
                    }
                    Bailian20231229.Client client = CreateClient();
                    Bailian20231229.Models.DeleteIndexResponse resp = DeleteIndex(client, workspaceId, indexId);
                    if (resp.Body.Status == "200")
                    {
                        Console.WriteLine($"Knowledge base {indexId} was deleted successfully.");
                    }
                    else
                    {
                        var mapper = new JsonSerializerSettings { Formatting = Formatting.Indented };
                        string errInfo = JsonConvert.SerializeObject(resp.Body, mapper);
                        Console.WriteLine($"An error occurred: {errInfo}");
                    }
                }
                else
                {
                    Console.WriteLine("Invalid option. Exiting.");
                    return;
                }
            }
            catch (Exception e)
            {
                Console.WriteLine("An error occurred: " + e.Message);
            }
        }
    }
}
```

## Go

```
// This sample code is for reference only. Do not use it in a production environment.
package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	bailian20231229 "github.com/alibabacloud-go/bailian-20231229/v2/client"
	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	util "github.com/alibabacloud-go/tea-utils/v2/service"
	"github.com/alibabacloud-go/tea/tea"
)

// checkEnvironmentVariables verifies that the required environment variables are set and reports any that are missing.
func checkEnvironmentVariables() bool {
	// The required environment variables and their descriptions.
	requiredVars := map[string]string{
		"ALIBABA_CLOUD_ACCESS_KEY_ID":     "Alibaba Cloud AccessKey ID",
		"ALIBABA_CLOUD_ACCESS_KEY_SECRET": "Alibaba Cloud AccessKey secret",
		"WORKSPACE_ID":                    "Alibaba Cloud Model Studio workspace ID",
	}

	var missingVars []string
	for varName, desc := range requiredVars {
		if os.Getenv(varName) == "" {
			fmt.Printf("Error: Set the %s environment variable (%s)\n", varName, desc)
			missingVars = append(missingVars, varName)
		}
	}

	return len(missingVars) == 0
}

// createClient creates and configures a client.
//
// Returns:
//   - *bailian20231229.Client: The configured client.
func createClient() (_result *bailian20231229.Client, _err error) {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
	}
	// This is a public cloud endpoint. Change this value to the endpoint for your region.
	config.Endpoint = tea.String("bailian.cn-beijing.aliyuncs.com")
	_result = &bailian20231229.Client{}
	_result, _err = bailian20231229.NewClient(config)
	return _result, _err
}

// listIndices lists the knowledge bases in a specified workspace.
//
// Parameters:
//   - client      *bailian20231229.Client: The client.
//   - workspaceId string: The workspace ID.
//
// Returns:
//   - *bailian20231229.ListIndicesResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: An error, if one occurred.
func listIndices(client *bailian20231229.Client, workspaceId string) (_result *bailian20231229.ListIndicesResponse, _err error) {
	headers := make(map[string]*string)
	listIndicesRequest := &bailian20231229.ListIndicesRequest{}
	runtime := &util.RuntimeOptions{}
	return client.ListIndicesWithOptions(tea.String(workspaceId), listIndicesRequest, headers, runtime)
}

// deleteIndex permanently deletes the specified knowledge base.
//
// Parameters:
//   - client      *bailian20231229.Client: The client.
//   - workspaceId string: The workspace ID.
//   - indexId     string: The knowledge base ID.
//
// Returns:
//   - *bailian20231229.DeleteIndexResponse: The response from the Alibaba Cloud Model Studio service.
//   - error: An error, if one occurred.
func deleteIndex(client *bailian20231229.Client, workspaceId, indexId string) (_result *bailian20231229.DeleteIndexResponse, _err error) {
	headers := make(map[string]*string)
	deleteIndexRequest := &bailian20231229.DeleteIndexRequest{
		IndexId: tea.String(indexId),
	}
	runtime := &util.RuntimeOptions{}
	return client.DeleteIndexWithOptions(tea.String(workspaceId), deleteIndexRequest, headers, runtime)

}

func main() {
	if !checkEnvironmentVariables() {
		fmt.Println("The environment variable check failed.")
		return
	}

	scanner := bufio.NewScanner(os.Stdin)
	fmt.Print("Select an operation:\n1. List knowledge bases\n2. Delete a knowledge base\nEnter an option (1 or 2): ")

	if !scanner.Scan() {
		fmt.Println("Failed to read input.")
		return
	}
	startOption := scanner.Text()

	client, err := createClient()
	if err != nil {
		fmt.Println("Failed to create the client:", err)
		return
	}

	if strings.TrimSpace(startOption) == "1" {
		fmt.Println("\nListing knowledge bases...")
		workspaceId := os.Getenv("WORKSPACE_ID")
		resp, err := listIndices(client, workspaceId)
		if err != nil {
			fmt.Println("Failed to get the list of knowledge bases:", err)
			return
		}
		fmt.Printf("Knowledge bases:\n%+v\n", resp.Body.Data)
	} else if strings.TrimSpace(startOption) == "2" {
		fmt.Println("\nDeleting a knowledge base...")
		workspaceId := os.Getenv("WORKSPACE_ID")
		fmt.Print("Enter the knowledge base ID: ")
		if !scanner.Scan() {
			fmt.Println("Failed to read the knowledge base ID.")
			return
		}
		indexId := scanner.Text()
		for {
			fmt.Printf("Are you sure you want to permanently delete knowledge base %s? (y/n): ", indexId)
			if !scanner.Scan() {
				fmt.Println("Failed to read confirmation.")
				return
			}
			confirm := strings.ToLower(strings.TrimSpace(scanner.Text()))

			if confirm == "y" {
				break
			} else if confirm == "n" {
				fmt.Println("Deletion canceled.")
				return
			} else {
				fmt.Println("Invalid input. Enter y or n.")
			}
		}
		resp, err := deleteIndex(client, workspaceId, indexId)
		if err != nil {
			fmt.Println("Failed to delete the knowledge base:", err)
		} else {
			if tea.StringValue(resp.Body.Status) == "200" {
				fmt.Printf("Knowledge base %s deleted successfully.\n", indexId)
			} else {
				fmt.Println(resp.Body)
			}
		}
	} else {
		fmt.Println("Invalid option. Exiting program.")
	}
}
```

## **Create a knowledge base**

Create a document search knowledge base in a specified workspace.

| ### **1\\. Initialize client** To upload files and create a knowledge base, first initialize a client. Use your [AccessKey and AccessKey Secret](#a4a15bd543can) to verify your identity and configure the `endpoint`. - **Public endpoints** > Your client must have internet access. - Public cloud: `bailian.cn-beijing.aliyuncs.com` - **VPC endpoints** > If your client is deployed on the public cloud in the Alibaba Cloud China (Beijing) region (`cn-beijing`) and is within a [VPC](https://help.aliyun.com/en/vpc/what-is-vpc), you can use the following VPC endpoint. Cross-region access is not supported. - Public cloud: `bailian-vpc.cn-beijing.aliyuncs.com` Creating the client returns a Client object for subsequent API calls. | ## Python ``` def create_client() -> bailian20231229Client: """ Create and configure a client. Returns: bailian20231229Client: The configured client. """ config = open_api_models.Config( access_key_id=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID'), access_key_secret=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET') ) # The following endpoint is an example of a public endpoint for the public cloud. You can change the endpoint as needed. config.endpoint = 'bailian.cn-beijing.aliyuncs.com' return bailian20231229Client(config) ``` ## Java ``` /** * Initialize a client. * * @return The configured client object. */ public com.aliyun.bailian20231229.Client createClient() throws Exception { com.aliyun.teaopenapi.models.Config config = new com.aliyun.teaopenapi.models.Config() .setAccessKeyId(System.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")) .setAccessKeySecret(System.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")); // The following endpoint is an example of a public endpoint for the public cloud. You can change the endpoint as needed. config.endpoint = "bailian.cn-beijing.aliyuncs.com"; return new com.aliyun.bailian20231229.Client(config); } ``` ## PHP ``` /** * Initialize a client. * * @return Bailian The configured client object. */ public function createClient(){ $config = new Config([ "accessKeyId" => getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"), "accessKeySecret" => getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") ]); // The following endpoint is an example of a public endpoint for the public cloud. You can change the endpoint as needed. $config->endpoint = 'bailian.cn-beijing.aliyuncs.com'; return new Bailian($config); } ``` ## Node.js ``` /** * Create and configure a client. * @return Client * @throws Exception */ function createClient() { const config = new OpenApi.Config({ accessKeyId: process.env.ALIBABA_CLOUD_ACCESS_KEY_ID, accessKeySecret: process.env.ALIBABA_CLOUD_ACCESS_KEY_SECRET }); // The following endpoint is an example of a public endpoint for the public cloud. You can change the endpoint as needed. config.endpoint = `bailian.cn-beijing.aliyuncs.com`; return new bailian20231229.default(config); } ``` ## C# ``` /// <summary> /// Initialize a client. /// </summary> /// <returns>The configured client object.</returns> /// <exception cref="Exception">Thrown when an error occurs during initialization.</exception> public AlibabaCloud.SDK.Bailian20231229.Client CreateClient() { var config = new AlibabaCloud.OpenApiClient.Models.Config { AccessKeyId = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_ID"), AccessKeySecret = Environment.GetEnvironmentVariable("ALIBABA_CLOUD_ACCESS_KEY_SECRET"), }; // The following endpoint is an example of a public endpoint for the public cloud. You can change the endpoint as needed. config.Endpoint = "bailian.cn-beijing.aliyuncs.com"; return new AlibabaCloud.SDK.Bailian20231229.Client(config); } ``` ## Go ``` // CreateClient creates and configures a client. // // Returns: // - *client.Bailian20231229Client: The configured client. // - error: The error message. func CreateClient() (_result *bailian20231229.Client, _err error) { config := &openapi.Config{ AccessKeyId: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")), AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")), } // The following endpoint is an example of a public endpoint for the public cloud. You can change the endpoint as needed. config.Endpoint = tea.String("bailian.cn-beijing.aliyuncs.com") _result = &bailian20231229.Client{} _result, _err = bailian20231229.NewClient(config) return _result, _err } ``` |
| --- | --- |
| ### **2\\. Upload knowledge base files** |   |
| #### **2.1. Request a file upload lease** Before creating a knowledge base, upload its source files to the **same workspace**. To do this, call the [ApplyFileUploadLease](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-applyfileuploadlease) operation to request a file upload lease. A lease is a temporary authorization to upload a file and is valid for several minutes. - **workspace\\_id:** See [How to obtain a workspace ID](https://help.aliyun.com/en/model-studio/use-workspace#c5222ec081sbo). - **category\\_id**: In this example, pass `default`. Model Studio uses categories to manage your uploaded files. The system automatically creates a default category. You can also call the [AddCategory API](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-addcategory) to create a new category and obtain the corresponding `category_id`. - **file\\_name:** Pass the name of the uploaded file, including its extension. The value must match the actual filename. For example, when you upload the file shown in the figure, pass `Alibaba_Cloud_Model_Studio_Mobile_Phone_Series_Introduction.docx`. ![image](https://help-static-aliyun-doc.aliyuncs.com/assets/img/en-US/2377286571/p904944.png) - **file\\_md5:** Pass the MD5 hash of the file to upload. Alibaba Cloud does not currently verify this value, which facilitates uploading files from a URL. > In Python, you can get the MD5 hash by using the hashlib module. For other languages, see the [complete sample code](#17d78ffbdafbj). **Code example** ``` import hashlib def calculate_md5(file_path): """ Calculate the MD5 hash of a file. Args: file_path (str): The local path of the file. Returns: str: The MD5 hash of the file. """ md5_hash = hashlib.md5() # Read the file in binary mode. with open(file_path, "rb") as f: # Read the file in chunks to avoid high memory usage for large files. for chunk in iter(lambda: f.read(4096), b""): md5_hash.update(chunk) return md5_hash.hexdigest() # Example usage file_path = "Replace this with the actual local path of the file to upload, for example, /path/to/your/Alibaba Cloud Model Studio Product Overview.docx" md5_value = calculate_md5(file_path) print(f"The MD5 hash of the file is: {md5_value}") ``` Replace the `file_path` variable in the code with the actual local path of the file and run the code to get the MD5 hash of the target file. The following is an example value: ``` The MD5 hash of the file is: 2ef7361ea907f3a1b91e3b9936f5643a ``` - **file\\_size:** Pass the size of the file to upload in bytes. > In Python, you can get this value by using the os module. For other languages, see the [complete sample code](#17d78ffbdafbj). **Code example** ``` import os def get_file_size(file_path: str) -> int: """ Get the size of a file in bytes. Args: file_path (str): The actual local path of the file. Returns: int: The file size in bytes. """ return os.path.getsize(file_path) # Example usage file_path = "Replace this with the actual local path of the file to upload, for example, /path/to/your/Alibaba Cloud Model Studio Product Overview.docx" file_size = get_file_size(file_path) print(f"The size of the file in bytes is: {file_size}") ``` Replace the `file_path` variable with the actual local path of the file and run the code to get the size of the target file in bytes. The following is an example value: ``` The size of the file in bytes is: 14015 ``` A successful request for a temporary upload lease returns the following: - **A set of temporary upload parameters:** - `Data.FileUploadLeaseId` - `Data.Param.Method` - `X-bailian-extra` in `Data.Param.Headers` - `Content-Type` in `Data.Param.Headers` - **Temporary upload URL:**`Data.Param.Url` | **Important** - Before calling this operation, a [RAM user](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) must be granted the required API permissions (the AliyunBailianDataFullAccess policy). - This operation supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/ApplyFileUploadLease) and [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/ApplyFileUploadLease?lang=JAVA&tab=DEMO) for multiple languages. ## Python ``` def apply_lease(client, category_id, file_name, file_md5, file_size, workspace_id): """ Request a file upload lease from Alibaba Cloud Model Studio. Args: client (bailian20231229Client): The client. category_id (str): The category ID. file_name (str): The file name. file_md5 (str): The MD5 hash of the file. file_size (int): The file size in bytes. workspace_id (str): The workspace ID. Returns: The response from Alibaba Cloud Model Studio. """ headers = {} request = bailian_20231229_models.ApplyFileUploadLeaseRequest( file_name=file_name, md_5=file_md5, size_in_bytes=file_size, ) runtime = util_models.RuntimeOptions() return client.apply_file_upload_lease_with_options(category_id, workspace_id, request, headers, runtime) ``` ## Java ``` /** * Request a file upload lease. * * @param client The client object. * @param categoryId The category ID. * @param fileName The file name. * @param fileMd5 The MD5 hash of the file. * @param fileSize The file size in bytes. * @param workspaceId The workspace ID. * @return The response object from Alibaba Cloud Model Studio. */ public ApplyFileUploadLeaseResponse applyLease(com.aliyun.bailian20231229.Client client, String categoryId, String fileName, String fileMd5, String fileSize, String workspaceId) throws Exception { Map<String, String> headers = new HashMap<>(); com.aliyun.bailian20231229.models.ApplyFileUploadLeaseRequest applyFileUploadLeaseRequest = new com.aliyun.bailian20231229.models.ApplyFileUploadLeaseRequest(); applyFileUploadLeaseRequest.setFileName(fileName); applyFileUploadLeaseRequest.setMd5(fileMd5); applyFileUploadLeaseRequest.setSizeInBytes(fileSize); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); ApplyFileUploadLeaseResponse applyFileUploadLeaseResponse = null; applyFileUploadLeaseResponse = client.applyFileUploadLeaseWithOptions(categoryId, workspaceId, applyFileUploadLeaseRequest, headers, runtime); return applyFileUploadLeaseResponse; } ``` ## PHP ``` /** * Request a file upload lease. * * @param Bailian $client The client. * @param string $categoryId The category ID. * @param string $fileName The file name. * @param string $fileMd5 The MD5 hash of the file. * @param int $fileSize The file size in bytes. * @param string $workspaceId The workspace ID. * @return ApplyFileUploadLeaseResponse The response from Alibaba Cloud Model Studio. */ public function applyLease($client, $categoryId, $fileName, $fileMd5, $fileSize, $workspaceId) { $headers = []; $applyFileUploadLeaseRequest = new ApplyFileUploadLeaseRequest([ "fileName" => $fileName, "md5" => $fileMd5, "sizeInBytes" => $fileSize ]); $runtime = new RuntimeOptions([]); return $client->applyFileUploadLeaseWithOptions($categoryId, $workspaceId, $applyFileUploadLeaseRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Request a file upload lease. * @param {Bailian20231229Client} client - The client. * @param {string} categoryId - The category ID. * @param {string} fileName - The file name. * @param {string} fileMd5 - The MD5 hash of the file. * @param {string} fileSize - The file size in bytes. * @param {string} workspaceId - The workspace ID. * @returns {Promise<bailian20231229.ApplyFileUploadLeaseResponse>} - The response from Alibaba Cloud Model Studio. */ async function applyLease(client, categoryId, fileName, fileMd5, fileSize, workspaceId) { const headers = {}; const req = new bailian20231229.ApplyFileUploadLeaseRequest({ md5: fileMd5, fileName, sizeInBytes: fileSize }); const runtime = new Util.RuntimeOptions({}); return await client.applyFileUploadLeaseWithOptions( categoryId, workspaceId, req, headers, runtime ); } ``` ## C# ``` /// <summary> /// Request a file upload lease. /// </summary> /// <param name="client">The client object.</param> /// <param name="categoryId">The category ID.</param> /// <param name="fileName">The file name.</param> /// <param name="fileMd5">The MD5 hash of the file.</param> /// <param name="fileSize">The file size in bytes.</param> /// <param name="workspaceId">The workspace ID.</param> /// <returns>The response object from Alibaba Cloud Model Studio.</returns> /// <exception cref="Exception">An exception is thrown if an error occurs during the call.</exception> public AlibabaCloud.SDK.Bailian20231229.Models.ApplyFileUploadLeaseResponse ApplyLease( AlibabaCloud.SDK.Bailian20231229.Client client, string categoryId, string fileName, string fileMd5, string fileSize, string workspaceId) { var headers = new Dictionary<string, string>() { }; var applyFileUploadLeaseRequest = new AlibabaCloud.SDK.Bailian20231229.Models.ApplyFileUploadLeaseRequest { FileName = fileName, Md5 = fileMd5, SizeInBytes = fileSize }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.ApplyFileUploadLeaseWithOptions(categoryId, workspaceId, applyFileUploadLeaseRequest, headers, runtime); } ``` ## Go ``` // ApplyLease requests a file upload lease from Alibaba Cloud Model Studio. // // Parameters: // - client (bailian20231229.Client): The client. // - categoryId (string): The category ID. // - fileName (string): The file name. // - fileMD5 (string): The MD5 hash of the file. // - fileSize (string): The file size in bytes. // - workspaceId (string): The workspace ID. // // Returns: // - *bailian20231229.ApplyFileUploadLeaseResponse: The response from Alibaba Cloud Model Studio. // - error: The error message. func ApplyLease(client *bailian20231229.Client, categoryId, fileName, fileMD5 string, fileSize string, workspaceId string) (_result *bailian20231229.ApplyFileUploadLeaseResponse, _err error) { headers := make(map[string]*string) applyFileUploadLeaseRequest := &bailian20231229.ApplyFileUploadLeaseRequest{ FileName: tea.String(fileName), Md5: tea.String(fileMD5), SizeInBytes: tea.String(fileSize), } runtime := &util.RuntimeOptions{} return client.ApplyFileUploadLeaseWithOptions(tea.String(categoryId), tea.String(workspaceId), applyFileUploadLeaseRequest, headers, runtime) } ``` **Request example** ``` { "CategoryId": "default", "FileName": "Alibaba Cloud Model Studio Product Overview.docx", "Md5": "2ef7361ea907f3a1b91e3b9936f5643a", "SizeInBytes": "14015", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx" } ``` **Response example** ``` { "RequestId": "778C0B3B-59C2-5FC1-A947-36EDD1XXXXXX", "Success": true, "Message": "", "Code": "success", "Status": "200", "Data": { "FileUploadLeaseId": "1e6a159107384782be5e45ac4759b247.1719325231035", "Type": "HTTP", "Param": { "Method": "PUT", "Url": "https://bailian-datahub-data-origin-prod.oss-cn-hangzhou.aliyuncs.com/1005426495169178/10024405/68abd1dea7b6404d8f7d7b9f7fbd332d.1716698936847.pdf?Expires=1716699536&OSSAccessKeyId=TestID&Signature=HfwPUZo4pR6DatSDym0zFKVh9Wg%3D", "Headers": " \\"X-bailian-extra\\": \\"MTAwNTQyNjQ5NTE2OTE3OA==\\",\\n \\"Content-Type\\": \\"application/pdf\\"" } } } ``` |
| #### **2.2. Upload file to temporary storage** With the upload lease, use the temporary upload parameters and URL to upload files from your local storage or a publicly accessible URL to the Model Studio server. Each workspace supports up to 100,000 files. The supported formats include PDF, DOCX, DOC, TXT, Markdown, PPTX, PPT, XLSX, XLS, HTML, PNG, JPG, JPEG, BMP, and GIF. - **pre\\_signed\\_url:** Specify the [Request a file upload lease](#9eb81df79bvkg) API response's `Data.Param.Url`. > This is a pre-signed URL and does not support FormData uploads. You must upload the file in binary format. For details, see the sample code. | **Important** This example does not support online debugging or sample code generation. ## Local upload ## Python ``` import requests from urllib.parse import urlparse def upload_file(pre_signed_url, file_path): """ Upload a local file to temporary storage. Args: pre_signed_url (str): The URL from the upload lease. file_path (str): The local path of the file. Returns: The response from Alibaba Cloud Model Studio. """ try: # Set the request headers. headers = { "X-bailian-extra": "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step.", "Content-Type": "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value." } # Read and upload the file. with open(file_path, 'rb') as file: # The request method for the file upload must be the same as the value of the Method field in Data.Param returned by the ApplyFileUploadLease operation in the previous step. response = requests.put(pre_signed_url, data=file, headers=headers) # Check the response status code. if response.status_code == 200: print("File uploaded successfully.") else: print(f"Failed to upload the file. ResponseCode: {response.status_code}") except Exception as e: print(f"An error occurred: {str(e)}") if __name__ == "__main__": pre_signed_url_or_http_url = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step." # Upload a local file to temporary storage. file_path = "Replace this with the actual local path of the file to upload, for example, on Linux: /path/to/your/Alibaba Cloud Model Studio Product Overview.docx" upload_file(pre_signed_url_or_http_url, file_path) ``` ## Java ``` import java.io.DataOutputStream; import java.io.FileInputStream; import java.net.HttpURLConnection; import java.net.URL; public class UploadFile { public static void uploadFile(String preSignedUrl, String filePath) { HttpURLConnection connection = null; try { // Create a URL object. URL url = new URL(preSignedUrl); connection = (HttpURLConnection) url.openConnection(); // The request method for the file upload must be the same as the value of the Method field in Data.Param returned by the ApplyFileUploadLease operation in the previous step. connection.setRequestMethod("PUT"); // Allow output to the connection because this connection is used to upload the file. connection.setDoOutput(true); connection.setRequestProperty("X-bailian-extra", "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step."); connection.setRequestProperty("Content-Type", "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value."); // Read the file and upload it through the connection. try (DataOutputStream outStream = new DataOutputStream(connection.getOutputStream()); FileInputStream fileInputStream = new FileInputStream(filePath)) { byte[] buffer = new byte[4096]; int bytesRead; while ((bytesRead = fileInputStream.read(buffer)) != -1) { outStream.write(buffer, 0, bytesRead); } outStream.flush(); } // Check the response. int responseCode = connection.getResponseCode(); if (responseCode == HttpURLConnection.HTTP_OK) { // The file was uploaded successfully. System.out.println("File uploaded successfully."); } else { // The file failed to be uploaded. System.out.println("Failed to upload the file. ResponseCode: " + responseCode); } } catch (Exception e) { e.printStackTrace(); } finally { if (connection != null) { connection.disconnect(); } } } public static void main(String[] args) { String preSignedUrlOrHttpUrl = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step."; // Upload a local file to temporary storage. String filePath = "Replace this with the actual local path of the file to upload, for example, on Linux: /path/to/your/Alibaba Cloud Model Studio Product Overview.docx"; uploadFile(preSignedUrlOrHttpUrl, filePath); } } ``` ## PHP ``` <?php /** * Upload a local file to temporary storage. * * @param string $preSignedUrl The pre-signed URL or HTTP address obtained from the ApplyFileUploadLease operation. * @param array $headers An array of request headers containing "X-bailian-extra" and "Content-Type". * @param string $filePath The local file path. * @throws Exception If the upload fails. */ function uploadFile($preSignedUrl, $headers, $filePath) { // Read the file content. $fileContent = file_get_contents($filePath); if ($fileContent === false) { throw new Exception("Cannot read the file: " . $filePath); } // Initialize a cURL session. $ch = curl_init(); // Set cURL options. curl_setopt($ch, CURLOPT_URL, $preSignedUrl); curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "PUT"); // Use the PUT method. curl_setopt($ch, CURLOPT_POSTFIELDS, $fileContent); // Set the request body to the file content. curl_setopt($ch, CURLOPT_RETURNTRANSFER, true); // Return the response instead of outputting it directly. // Build the request headers. $uploadHeaders = [ "X-bailian-extra: " . $headers["X-bailian-extra"], "Content-Type: " . $headers["Content-Type"] ]; curl_setopt($ch, CURLOPT_HTTPHEADER, $uploadHeaders); // Execute the request. $response = curl_exec($ch); // Get the HTTP status code. $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE); // Close the cURL session. curl_close($ch); // Check the response code. if ($httpCode != 200) { throw new Exception("Upload failed. HTTP status code: " . $httpCode . ", error message: " . $response); } // The upload is successful. echo "File uploaded successfully.\\n"; } /** * Main function: Upload a local file. */ function main() { // Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step. $preSignedUrl = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step."; // Replace these with the values of X-bailian-extra and Content-Type in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. $headers = [ "X-bailian-extra" => "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step.", "Content-Type" => "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value." ]; // Upload a local file to temporary storage. $filePath = "Replace this with the actual local path of the file to upload, for example, on Linux: /path/to/your/Alibaba Cloud Model Studio Product Overview.docx"; try { uploadFile($preSignedUrl, $headers, $filePath); } catch (Exception $e) { echo "Error: " . $e->getMessage() . "\\n"; } } // Call the main function. main(); ?> ``` ## Node.js ``` const fs = require('fs'); const axios = require('axios'); /** * Upload a local file to temporary storage. * * @param {string} preSignedUrl - The URL from the upload lease. * @param {Object} headers - The headers for the upload request. * @param {string} filePath - The local path of the file. * @throws {Error} If the upload fails. */ async function uploadFile(preSignedUrl, headers, filePath) { // Build the request headers required for the upload. const uploadHeaders = { "X-bailian-extra": headers["X-bailian-extra"], "Content-Type": headers["Content-Type"] }; // Create a file read stream. const fileStream = fs.createReadStream(filePath); try { // Use axios to send a PUT request. const response = await axios.put(preSignedUrl, fileStream, { headers: uploadHeaders }); // Check the response status code. if (response.status === 200) { console.log("File uploaded successfully."); } else { console.error(`Failed to upload the file. ResponseCode: ${response.status}`); throw new Error(`Upload failed with status code: ${response.status}`); } } catch (error) { // Handle errors. console.error("Error during upload:", error.message); throw new Error(`Upload failed: ${error.message}`); } } /** * Main function: Upload a local file. */ function main() { const preSignedUrl = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step."; const headers = { "X-bailian-extra": "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step.", "Content-Type": "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value." }; // Upload a local file to temporary storage. const filePath = "Replace this with the actual local path of the file to upload, for example, on Linux: /path/to/your/Alibaba Cloud Model Studio Product Overview.docx"; uploadFile(preSignedUrl, headers, filePath) .then(() => { console.log("Upload completed."); }) .catch((err) => { console.error("Upload failed:", err.message); }); } // Call the main function. main(); ``` ## C# ``` using System; using System.IO; using System.Net; public class UploadFilExample { public static void UploadFile(string preSignedUrl, string filePath) { HttpWebRequest connection = null; try { // Create a URL object. Uri url = new Uri(preSignedUrl); connection = (HttpWebRequest)WebRequest.Create(url); // The request method for the file upload must be the same as the value of the Method field in Data.Param returned by the ApplyFileUploadLease operation in the previous step. connection.Method = "PUT"; // Allow output to the connection because this connection is used to upload the file. connection.AllowWriteStreamBuffering = false; connection.SendChunked = false; // Set the request headers to be the same as the field values in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. connection.Headers["X-bailian-extra"] = "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step."; connection.ContentType = "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value."; // Read the file and upload it through the connection. using (var fileStream = new FileStream(filePath, FileMode.Open, FileAccess.Read)) using (var requestStream = connection.GetRequestStream()) { byte[] buffer = new byte[4096]; int bytesRead; while ((bytesRead = fileStream.Read(buffer, 0, buffer.Length)) != 0) { requestStream.Write(buffer, 0, bytesRead); } requestStream.Flush(); } // Check the response. using (HttpWebResponse response = (HttpWebResponse)connection.GetResponse()) { if (response.StatusCode == HttpStatusCode.OK) { // The file was uploaded successfully. Console.WriteLine("File uploaded successfully."); } else { // The file failed to be uploaded. Console.WriteLine($"Failed to upload the file. ResponseCode: {response.StatusCode}"); } } } catch (Exception e) { Console.WriteLine(e.Message); e.StackTrace.ToString(); } finally { if (connection != null) { connection.Abort(); } } } public static void Main(string[] args) { string preSignedUrlOrHttpUrl = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step."; // Upload a local file to temporary storage. string filePath = "Replace this with the actual local path of the file to upload, for example, on Linux: /path/to/your/Alibaba Cloud Model Studio Product Overview.docx"; UploadFile(preSignedUrlOrHttpUrl, filePath); } } ``` ## Go ``` package main import ( "fmt" "io" "os" "github.com/go-resty/resty/v2" ) // UploadFile uploads a local file to temporary storage. // // Parameters: // - preSignedUrl (string): The URL from the upload lease. // - headers (map[string]string): The headers for the upload request. // - filePath (string): The local path of the file. // // Returns: // - error: An error message if the upload fails, otherwise nil. func UploadFile(preSignedUrl string, headers map[string]string, filePath string) error { // Open the local file. file, err := os.Open(filePath) if err != nil { return fmt.Errorf("failed to open file: %w", err) } defer file.Close() // Read the content. body, err := io.ReadAll(file) if err != nil { return fmt.Errorf("failed to read file: %w", err) } // Create a REST client. client := resty.New() // Build the request headers required for the upload. uploadHeaders := map[string]string{ "X-bailian-extra": headers["X-bailian-extra"], "Content-Type": headers["Content-Type"], } // Send a PUT request. resp, err := client.R(). SetHeaders(uploadHeaders). SetBody(body). Put(preSignedUrl) if err != nil { return fmt.Errorf("failed to send request: %w", err) } // Check the HTTP response status code. if resp.IsError() { return fmt.Errorf("HTTP error: %d", resp.StatusCode()) } fmt.Println("File uploaded successfully.") return nil } // main function func main() { // Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step. preSignedUrl := "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step." // Replace these with the values of X-bailian-extra and Content-Type in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. headers := map[string]string{ "X-bailian-extra": "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step.", "Content-Type": "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value.", } // Upload a local file to temporary storage. filePath := "Replace this with the actual local path of the file to upload, for example, on Linux: /path/to/your/Alibaba Cloud Model Studio Product Overview.docx" // Call the upload function. err := UploadFile(preSignedUrl, headers, filePath) if err != nil { fmt.Printf("Upload failed: %v\\n", err) } } ``` ## URL upload > The URL must be publicly accessible and point to a valid file. ## Python ``` import requests from urllib.parse import urlparse def upload_file_link(pre_signed_url, source_url_string): """ Upload a file from a public URL to temporary storage. Args: pre_signed_url (str): The URL from the upload lease. source_url_string (str): The URL of the file. Returns: The response from Alibaba Cloud Model Studio. """ try: # Set the request headers. headers = { "X-bailian-extra": "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step.", "Content-Type": "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value." } # Set the request method to GET to access the file URL. source_response = requests.get(source_url_string) if source_response.status_code != 200: raise RuntimeError("Failed to get source file.") # The request method for the file upload must be the same as the value of the Method field in Data.Param returned by the ApplyFileUploadLease operation in the previous step. response = requests.put(pre_signed_url, data=source_response.content, headers=headers) # Check the response status code. if response.status_code == 200: print("File uploaded successfully.") else: print(f"Failed to upload the file. ResponseCode: {response.status_code}") except Exception as e: print(f"An error occurred: {str(e)}") if __name__ == "__main__": pre_signed_url_or_http_url = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step." # The URL of the file. source_url = "Replace this with the URL of the file to upload." upload_file_link(pre_signed_url_or_http_url, source_url) ``` ## Java ``` import java.io.BufferedInputStream; import java.io.DataOutputStream; import java.io.InputStream; import java.net.HttpURLConnection; import java.net.URL; public class UploadFile { public static void uploadFileLink(String preSignedUrl, String sourceUrlString) { HttpURLConnection connection = null; try { // Create a URL object. URL url = new URL(preSignedUrl); connection = (HttpURLConnection) url.openConnection(); // The request method for the file upload must be the same as the value of the Method field in Data.Param returned by the ApplyFileUploadLease operation in the previous step. connection.setRequestMethod("PUT"); // Allow output to the connection because this connection is used to upload the file. connection.setDoOutput(true); connection.setRequestProperty("X-bailian-extra", "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step."); connection.setRequestProperty("Content-Type", "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value."); URL sourceUrl = new URL(sourceUrlString); HttpURLConnection sourceConnection = (HttpURLConnection) sourceUrl.openConnection(); // Set the request method to GET to access the file URL. sourceConnection.setRequestMethod("GET"); // Get the response code. 200 indicates that the request was successful. int sourceFileResponseCode = sourceConnection.getResponseCode(); // Read the file from the URL and upload it through the connection. if (sourceFileResponseCode != HttpURLConnection.HTTP_OK) { throw new RuntimeException("Failed to get source file."); } try (DataOutputStream outStream = new DataOutputStream(connection.getOutputStream()); InputStream in = new BufferedInputStream(sourceConnection.getInputStream())) { byte[] buffer = new byte[4096]; int bytesRead; while ((bytesRead = in.read(buffer)) != -1) { outStream.write(buffer, 0, bytesRead); } outStream.flush(); } // Check the response. int responseCode = connection.getResponseCode(); if (responseCode == HttpURLConnection.HTTP_OK) { // The file was uploaded successfully. System.out.println("File uploaded successfully."); } else { // The file failed to be uploaded. System.out.println("Failed to upload the file. ResponseCode: " + responseCode); } } catch (Exception e) { e.printStackTrace(); } finally { if (connection != null) { connection.disconnect(); } } } public static void main(String[] args) { String preSignedUrlOrHttpUrl = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step."; String sourceUrl = "Replace this with the URL of the file to upload."; uploadFileLink(preSignedUrlOrHttpUrl, sourceUrl); } } ``` ## PHP ``` <?php /** * Upload a file from a public URL to temporary storage. * * @param string $preSignedUrl The pre-signed URL or HTTP address obtained from the ApplyFileUploadLease operation. * @param array $headers An array of request headers containing "X-bailian-extra" and "Content-Type". * @param string $sourceUrl The URL of the file. * @throws Exception If the upload fails. */ function uploadFile($preSignedUrl, $headers, $sourceUrl) { $fileContent = file_get_contents($sourceUrl); if ($fileContent === false) { throw new Exception("Cannot download the file from the given URL: " . $sourceUrl); } // Initialize a cURL session. $ch = curl_init(); // Set cURL options. curl_setopt($ch, CURLOPT_URL, $preSignedUrl); curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "PUT"); // Use the PUT method. curl_setopt($ch, CURLOPT_POSTFIELDS, $fileContent); // Set the request body to the file content. curl_setopt($ch, CURLOPT_RETURNTRANSFER, true); // Return the response instead of outputting it directly. // Build the request headers. $uploadHeaders = [ "X-bailian-extra: " . $headers["X-bailian-extra"], "Content-Type: " . $headers["Content-Type"] ]; curl_setopt($ch, CURLOPT_HTTPHEADER, $uploadHeaders); // Execute the request. $response = curl_exec($ch); // Get the HTTP status code. $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE); // Close the cURL session. curl_close($ch); // Check the response code. if ($httpCode != 200) { throw new Exception("Upload failed. HTTP status code: " . $httpCode . ", error message: " . $response); } // The upload is successful. echo "File uploaded successfully.\\n"; } /** * Main function: Upload a file from a public URL to temporary storage. */ function main() { // Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step. $preSignedUrl = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step."; // Replace these with the values of X-bailian-extra and Content-Type in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. $headers = [ "X-bailian-extra" => "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step.", "Content-Type" => "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value." ]; $sourceUrl = "Replace this with the URL of the file to upload."; try { uploadFile($preSignedUrl, $headers, $sourceUrl); } catch (Exception $e) { echo "Error: " . $e->getMessage() . "\\n"; } } // Call the main function. main(); ?> ``` ## Node.js ``` const axios = require('axios'); /** * Upload a file from a public URL to temporary storage. * * @param {string} preSignedUrl - The URL from the upload lease. * @param {Object} headers - The headers for the upload request. * @param {string} sourceUrl - The URL of the file. * @throws {Error} If the upload fails. */ async function uploadFileFromUrl(preSignedUrl, headers, sourceUrl) { // Build the request headers required for the upload. const uploadHeaders = { "X-bailian-extra": headers["X-bailian-extra"], "Content-Type": headers["Content-Type"] }; try { // Download the file from the given URL. const response = await axios.get(sourceUrl, { responseType: 'stream' }); // Use axios to send a PUT request. const uploadResponse = await axios.put(preSignedUrl, response.data, { headers: uploadHeaders }); // Check the response status code. if (uploadResponse.status === 200) { console.log("File uploaded successfully from URL."); } else { console.error(`Failed to upload the file. ResponseCode: ${uploadResponse.status}`); throw new Error(`Upload failed with status code: ${uploadResponse.status}`); } } catch (error) { // Handle errors. console.error("Error during upload:", error.message); throw new Error(`Upload failed: ${error.message}`); } } /** * Main function: Upload a publicly downloadable file to temporary storage. */ function main() { const preSignedUrl = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step."; const headers = { "X-bailian-extra": "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step.", "Content-Type": "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value." }; const sourceUrl = "Replace this with the URL of the file to upload."; uploadFileFromUrl(preSignedUrl, headers, sourceUrl) .then(() => { console.log("Upload completed."); }) .catch((err) => { console.error("Upload failed:", err.message); }); } // Call the main function. main(); ``` ## C# ``` using System; using System.IO; using System.Net; using System.Net.Http; using System.Threading.Tasks; public class UploadFileExample { public static async Task UploadFileFromUrl(string preSignedUrl, string url) { try { // Create an HTTP client to download the file from the given URL. using (HttpClient httpClient = new HttpClient()) { HttpResponseMessage response = await httpClient.GetAsync(url, HttpCompletionOption.ResponseHeadersRead); response.EnsureSuccessStatusCode(); // Get the file stream. using (Stream fileStream = await response.Content.ReadAsStreamAsync()) { // Create a URL object. Uri urlObj = new Uri(preSignedUrl); HttpWebRequest connection = (HttpWebRequest)WebRequest.Create(urlObj); // Set the request method for file upload. connection.Method = "PUT"; connection.AllowWriteStreamBuffering = false; connection.SendChunked = false; // Set the request headers. Replace with actual values. connection.Headers["X-bailian-extra"] = "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step."; connection.ContentType = "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value."; // Get the request stream and write the file stream to it. using (Stream requestStream = connection.GetRequestStream()) { byte[] buffer = new byte[4096]; int bytesRead; while ((bytesRead = await fileStream.ReadAsync(buffer, 0, buffer.Length)) > 0) { await requestStream.WriteAsync(buffer, 0, bytesRead); } await requestStream.FlushAsync(); } // Check the response. using (HttpWebResponse responseResult = (HttpWebResponse)connection.GetResponse()) { if (responseResult.StatusCode == HttpStatusCode.OK) { Console.WriteLine("File uploaded successfully from URL."); } else { Console.WriteLine($"Failed to upload the file. ResponseCode: {responseResult.StatusCode}"); } } } } } catch (Exception e) { Console.WriteLine(e.Message); Console.WriteLine(e.StackTrace); } } public static async Task Main(string[] args) { string preSignedUrlOrHttpUrl = "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step."; string url = "Replace this with the URL of the file to upload."; await UploadFileFromUrl(preSignedUrlOrHttpUrl, url); } } ``` ## Go ``` package main import ( "fmt" "net/http" "github.com/go-resty/resty/v2" ) // UploadFileFromUrl uploads a file from a public URL to temporary storage. // // Parameters: // - preSignedUrl (string): The URL from the upload lease. // - headers (map[string]string): The headers for the upload request. // - sourceUrl (string): The URL of the file. // // Returns: // - error: An error message if the upload fails, otherwise nil. func UploadFileFromUrl(preSignedUrl string, headers map[string]string, sourceUrl string) error { // Download the file from the given URL. resp, err := http.Get(sourceUrl) if err != nil { return fmt.Errorf("failed to get file: %w", err) } defer resp.Body.Close() if resp.StatusCode != http.StatusOK { return fmt.Errorf("failed to get file, status code: %d", resp.StatusCode) } // Create a REST client. client := resty.New() // Build the request headers required for the upload. uploadHeaders := map[string]string{ "X-bailian-extra": headers["X-bailian-extra"], "Content-Type": headers["Content-Type"], } // Send a PUT request. response, err := client.R(). SetHeaders(uploadHeaders). SetBody(resp.Body). Put(preSignedUrl) if err != nil { return fmt.Errorf("failed to send request: %w", err) } if err != nil { return fmt.Errorf("failed to send request: %w", err) } // Check the HTTP response status code. if response.IsError() { return fmt.Errorf("HTTP error: %d", response.StatusCode()) } fmt.Println("File uploaded successfully from URL.") return nil } // main function func main() { // Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step. preSignedUrl := "Replace this with the value of the Url field in Data.Param returned by the ApplyFileUploadLease operation in the previous step." // Replace these with the values of X-bailian-extra and Content-Type in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. headers := map[string]string{ "X-bailian-extra": "Replace this with the value of the X-bailian-extra field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step.", "Content-Type": "Replace this with the value of the Content-Type field in Data.Param.Headers returned by the ApplyFileUploadLease operation in the previous step. If a null value is returned, pass a null value.", } sourceUrl := "Replace this with the URL of the file to upload." // Call the upload function. err := UploadFileFromUrl(preSignedUrl, headers, sourceUrl) if err != nil { fmt.Printf("Upload failed: %v\\n", err) } } ``` |
| #### **2.3. Add file to a category** After uploading the file, add it to a category in the same workspace by calling the [AddFile](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-addfile) operation. - **parser:** Specify `DASHSCOPE_DOCMIND`. - **lease\\_id:** Set this parameter to the `Data.FileUploadLeaseId` that is returned when you [request a file upload lease](#9eb81df79bvkg). - **category\\_id:** In this example, pass `default`. If you use a custom category for uploads, you must pass the corresponding `category_id`. **Important** The `CategoryId` passed here must match the `CategoryId` used in the [Apply for a file upload lease](#9eb81df79bvkg) step. Otherwise, you will receive a `Category is mismatched` error. After you add a file, Model Studio returns a `FileId` for the file and automatically starts parsing it. The `lease_id` is immediately invalidated. **Do not reuse the same lease ID for another submission.** | **Important** - Before calling this operation, a [RAM user](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) must be granted the required API permissions (the AliyunBailianDataFullAccess policy). - This operation supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/AddFile) and [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/AddFile?lang=JAVA&tab=DEMO) for multiple languages. ## Python ``` def add_file(client: bailian20231229Client, lease_id: str, parser: str, category_id: str, workspace_id: str): """ Add a file to a specified category in Alibaba Cloud Model Studio. Args: client (bailian20231229Client): The client. lease_id (str): The lease ID. parser (str): The parser for the file. category_id (str): The category ID. workspace_id (str): The workspace ID. Returns: The response from Alibaba Cloud Model Studio. """ headers = {} request = bailian_20231229_models.AddFileRequest( lease_id=lease_id, parser=parser, category_id=category_id, ) runtime = util_models.RuntimeOptions() return client.add_file_with_options(workspace_id, request, headers, runtime) ``` ## Java ``` /** * Add a file to a category. * * @param client The client object. * @param leaseId The lease ID. * @param parser The parser for the file. * @param categoryId The category ID. * @param workspaceId The workspace ID. * @return The response object from Alibaba Cloud Model Studio. */ public AddFileResponse addFile(com.aliyun.bailian20231229.Client client, String leaseId, String parser, String categoryId, String workspaceId) throws Exception { Map<String, String> headers = new HashMap<>(); com.aliyun.bailian20231229.models.AddFileRequest addFileRequest = new com.aliyun.bailian20231229.models.AddFileRequest(); addFileRequest.setLeaseId(leaseId); addFileRequest.setParser(parser); addFileRequest.setCategoryId(categoryId); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); return client.addFileWithOptions(workspaceId, addFileRequest, headers, runtime); } ``` ## PHP ``` /** * Add a file to a category. * * @param Bailian $client The client. * @param string $leaseId The lease ID. * @param string $parser The parser for the file. * @param string $categoryId The category ID. * @param string $workspaceId The workspace ID. * @return AddFileResponse The response from Alibaba Cloud Model Studio. */ public function addFile($client, $leaseId, $parser, $categoryId, $workspaceId) { $headers = []; $addFileRequest = new AddFileRequest([ "leaseId" => $leaseId, "parser" => $parser, "categoryId" => $categoryId ]); $runtime = new RuntimeOptions([]); return $client->addFileWithOptions($workspaceId, $addFileRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Add a file to a category. * @param {Bailian20231229Client} client - The client. * @param {string} leaseId - The lease ID. * @param {string} parser - The parser for the file. * @param {string} categoryId - The category ID. * @param {string} workspaceId - The workspace ID. * @returns {Promise<bailian20231229.AddFileResponse>} - The response from Alibaba Cloud Model Studio. */ async function addFile(client, leaseId, parser, categoryId, workspaceId) { const headers = {}; const req = new bailian20231229.AddFileRequest({ leaseId, parser, categoryId }); const runtime = new Util.RuntimeOptions({}); return await client.addFileWithOptions(workspaceId, req, headers, runtime); } ``` ## C# ``` /// <summary> /// Add a file to a category. /// </summary> /// <param name="client">The client object.</param> /// <param name="leaseId">The lease ID.</param> /// <param name="parser">The parser for the file.</param> /// <param name="categoryId">The category ID.</param> /// <param name="workspaceId">The workspace ID.</param> /// <returns>The response object from Alibaba Cloud Model Studio.</returns> /// <exception cref="Exception">An exception is thrown if an error occurs during the call.</exception> public AlibabaCloud.SDK.Bailian20231229.Models.AddFileResponse AddFile( AlibabaCloud.SDK.Bailian20231229.Client client, string leaseId, string parser, string categoryId, string workspaceId) { var headers = new Dictionary<string, string>() { }; var addFileRequest = new AlibabaCloud.SDK.Bailian20231229.Models.AddFileRequest { LeaseId = leaseId, Parser = parser, CategoryId = categoryId }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.AddFileWithOptions(workspaceId, addFileRequest, headers, runtime); } ``` ## Go ``` // AddFile adds a file to a specified category in Alibaba Cloud Model Studio. // // Parameters: // - client (bailian20231229.Client): The client. // - leaseId (string): The lease ID. // - parser (string): The parser for the file. // - categoryId (string): The category ID. // - workspaceId (string): The workspace ID. // // Returns: // - *bailian20231229.AddFileResponse: The response from Alibaba Cloud Model Studio. // - error: The error message. func AddFile(client *bailian20231229.Client, leaseId, parser, categoryId, workspaceId string) (_result *bailian20231229.AddFileResponse, _err error) { headers := make(map[string]*string) addFileRequest := &bailian20231229.AddFileRequest{ LeaseId: tea.String(leaseId), Parser: tea.String(parser), CategoryId: tea.String(categoryId), } runtime := &util.RuntimeOptions{} return client.AddFileWithOptions(tea.String(workspaceId), addFileRequest, headers, runtime) } ``` **Request example** ``` { "CategoryId": "default", "LeaseId": "d92bd94fa9b54326a2547415e100c9e2.1742195250069", "Parser": "DASHSCOPE_DOCMIND", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx" } ``` **Response example** ``` { "Status": "200", "Message": "", "RequestId": "5832A1F4-AF91-5242-8B75-35BDC9XXXXXX", "Data": { "FileId": "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx", "Parser": "DASHSCOPE_DOCMIND" }, "Code": "Success", "Success": "true" } ``` |
| #### **2.4. Query file parsing status** A file cannot be used in a knowledge base until it is parsed. During peak hours, this process can take several hours. You can call the [DescribeFile](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-describefile) operation to query its parsing status. - **file\\_id:** Specify the `FileId` returned by the API when you [add a file to a category](#494345d4b1hx2). If the `Data.Status` field is `PARSE_SUCCESS`, the file has been successfully parsed and you can import it into the knowledge base. | **Important** - Before calling this operation, a [RAM user](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) must be granted the required API permissions (the AliyunBailianDataFullAccess or AliyunBailianDataReadOnlyAccess policy). - This operation supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/DescribeFile) and [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/DescribeFile?lang=JAVA&tab=DEMO) for multiple languages. ## Python ``` def describe_file(client, workspace_id, file_id): """ Get the basic information of a file. Args: client (bailian20231229Client): The client. workspace_id (str): The workspace ID. file_id (str): The file ID. Returns: The response from Alibaba Cloud Model Studio. """ headers = {} runtime = util_models.RuntimeOptions() return client.describe_file_with_options(workspace_id, file_id, headers, runtime) ``` ## Java ``` /** * Query the basic information of a file. * * @param client The client object. * @param workspaceId The workspace ID. * @param fileId The file ID. * @return The response object from Alibaba Cloud Model Studio. */ public DescribeFileResponse describeFile(com.aliyun.bailian20231229.Client client, String workspaceId, String fileId) throws Exception { Map<String, String> headers = new HashMap<>(); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); return client.describeFileWithOptions(workspaceId, fileId, headers, runtime); } ``` ## PHP ``` /** * Query the basic information of a file. * * @param Bailian $client The client. * @param string $workspaceId The workspace ID. * @param string $fileId The file ID. * @return DescribeFileResponse The response from Alibaba Cloud Model Studio. */ public function describeFile($client, $workspaceId, $fileId) { $headers = []; $runtime = new RuntimeOptions([]); return $client->describeFileWithOptions($workspaceId, $fileId, $headers, $runtime); } ``` ## Node.js ``` /** * Query the parsing status of a file. * @param {Bailian20231229Client} client - The client. * @param {string} workspaceId - The workspace ID. * @param {string} fileId - The file ID. * @returns {Promise<bailian20231229.DescribeFileResponse>} - The response from Alibaba Cloud Model Studio. */ async function describeFile(client, workspaceId, fileId) { const headers = {}; const runtime = new Util.RuntimeOptions({}); return await client.describeFileWithOptions(workspaceId, fileId, headers, runtime); } ``` ## C# ``` /// <summary> /// Query the basic information of a file. /// </summary> /// <param name="client">The client object.</param> /// <param name="workspaceId">The workspace ID.</param> /// <param name="fileId">The file ID.</param> /// <returns>The response object from Alibaba Cloud Model Studio.</returns> /// <exception cref="Exception">An exception is thrown if an error occurs during the call.</exception> public AlibabaCloud.SDK.Bailian20231229.Models.DescribeFileResponse DescribeFile( AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string fileId) { var headers = new Dictionary<string, string>() { }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.describeFileWithOptions(workspaceId, fileId, headers, runtime); } ``` ## Go ``` // DescribeFile gets the basic information of a file. // // Parameters: // - client (bailian20231229.Client): The client. // - workspaceId (string): The workspace ID. // - fileId (string): The file ID. // // Returns: // - *bailian20231229.DescribeFileResponse: The response from Alibaba Cloud Model Studio. // - error: The error message. func DescribeFile(client *bailian20231229.Client, workspaceId, fileId string) (_result *bailian20231229.DescribeFileResponse, _err error) { headers := make(map[string]*string) runtime := &util.RuntimeOptions{} return client.DescribeFileWithOptions(tea.String(workspaceId), tea.String(fileId), headers, runtime) } ``` **Request example** ``` { "FileId": "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx" } ``` **Response example** ``` { "Status": "200", "Message": "", "RequestId": "B9246251-987A-5628-8E1E-17BB39XXXXXX", "Data": { "CategoryId": "cate_206ea350f0014ea4a324adff1ca13011_10xxxxxx", "Status": "PARSE_SUCCESS", "FileType": "docx", "CreateTime": "2025-03-17 15:47:13", "FileName": "Alibaba Cloud Model Studio Product Overview.docx", "FileId": "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx", "SizeInBytes": "14015", "Parser": "DASHSCOPE_DOCMIND" }, "Code": "Success", "Success": "true" } ``` |
| ### **3\\. Create a knowledge base** |   |
| #### **3.1. Initialize knowledge base** Once a file is parsed, you can create a knowledge base from it in the same workspace. To begin, call the [CreateIndex](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-createindex) operation to initialize (but not finalize) a document retrieval knowledge base. - **workspace\\_id:** See [How to obtain a workspace ID](https://help.aliyun.com/en/model-studio/use-workspace#c5222ec081sbo). - **file\\_id:** Specify the `FileId` returned by the API when you [add a file to a category](#494345d4b1hx2). > If `source_type` is set to `DATA_CENTER_FILE`, this parameter is required, and the API returns an error if it is not specified. - **structure\\_type:** In this example, pass `unstructured`. - **source\\_type:** In this example, pass `DATA_CENTER_FILE`. - **sink\\_type:** In this example, specify `BUILT_IN`. The value of the `Data.Id` field returned by this API is the knowledge base ID, which is used for subsequent index building. > Keep the knowledge base ID secure, as it is required for all subsequent API operations related to this knowledge base. | **Important** - Before calling this operation, a [RAM user](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) must be granted the required API permissions (the AliyunBailianDataFullAccess policy). - This operation supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/CreateIndex) and [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/CreateIndex?lang=JAVA&tab=DEMO) for multiple languages. ## Python ``` def create_index(client, workspace_id, file_id, name, structure_type, source_type, sink_type): """ Create (initialize) a knowledge base in Alibaba Cloud Model Studio. Args: client (bailian20231229Client): The client. workspace_id (str): The workspace ID. file_id (str): The file ID. name (str): The name of the knowledge base. structure_type (str): The data structure type of the knowledge base. source_type (str): The data source type. Category and file types are supported. sink_type (str): The vector storage type of the knowledge base. Returns: The response from Alibaba Cloud Model Studio. """ headers = {} request = bailian_20231229_models.CreateIndexRequest( structure_type=structure_type, name=name, source_type=source_type, sink_type=sink_type, document_ids=[file_id] ) runtime = util_models.RuntimeOptions() return client.create_index_with_options(workspace_id, request, headers, runtime) ``` ## Java ``` /** * Create (initialize) a knowledge base in Alibaba Cloud Model Studio. * * @param client The client object. * @param workspaceId The workspace ID. * @param fileId The file ID. * @param name The name of the knowledge base. * @param structureType The data structure type of the knowledge base. * @param sourceType The data source type. Category and file types are supported. * @param sinkType The vector storage type of the knowledge base. * @return The response object from Alibaba Cloud Model Studio. */ public CreateIndexResponse createIndex(com.aliyun.bailian20231229.Client client, String workspaceId, String fileId, String name, String structureType, String sourceType, String sinkType) throws Exception { Map<String, String> headers = new HashMap<>(); com.aliyun.bailian20231229.models.CreateIndexRequest createIndexRequest = new com.aliyun.bailian20231229.models.CreateIndexRequest(); createIndexRequest.setStructureType(structureType); createIndexRequest.setName(name); createIndexRequest.setSourceType(sourceType); createIndexRequest.setSinkType(sinkType); createIndexRequest.setDocumentIds(Collections.singletonList(fileId)); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); return client.createIndexWithOptions(workspaceId, createIndexRequest, headers, runtime); } ``` ## PHP ``` /** * Create (initialize) a knowledge base in Alibaba Cloud Model Studio. * * @param Bailian $client The client. * @param string $workspaceId The workspace ID. * @param string $fileId The file ID. * @param string $name The name of the knowledge base. * @param string $structureType The data structure type of the knowledge base. * @param string $sourceType The data source type. Category and file types are supported. * @param string $sinkType The vector storage type of the knowledge base. * @return CreateIndexResponse The response from Alibaba Cloud Model Studio. */ public function createIndex($client, $workspaceId, $fileId, $name, $structureType, $sourceType, $sinkType) { $headers = []; $createIndexRequest = new CreateIndexRequest([ "structureType" => $structureType, "name" => $name, "sourceType" => $sourceType, "documentIds" => [ $fileId ], "sinkType" => $sinkType ]); $runtime = new RuntimeOptions([]); return $client->createIndexWithOptions($workspaceId, $createIndexRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Initialize a knowledge base (index). * @param {Bailian20231229Client} client - The client. * @param {string} workspaceId - The workspace ID. * @param {string} fileId - The file ID. * @param {string} name - The name of the knowledge base. * @param {string} structureType - The data structure type of the knowledge base. * @param {string} sourceType - The data source type. Category and file types are supported. * @param {string} sinkType - The vector storage type of the knowledge base. * @returns {Promise<bailian20231229.CreateIndexResponse>} - The response from Alibaba Cloud Model Studio. */ async function createIndex(client, workspaceId, fileId, name, structureType, sourceType, sinkType) { const headers = {}; const req = new bailian20231229.CreateIndexRequest({ name, structureType, documentIds: [fileId], sourceType, sinkType }); const runtime = new Util.RuntimeOptions({}); return await client.createIndexWithOptions(workspaceId, req, headers, runtime); } ``` ## C# ``` /// <summary> /// Create (initialize) a knowledge base in Alibaba Cloud Model Studio. /// </summary> /// <param name="client">The client object.</param> /// <param name="workspaceId">The workspace ID.</param> /// <param name="fileId">The file ID.</param> /// <param name="name">The name of the knowledge base.</param> /// <param name="structureType">The data structure type of the knowledge base.</param> /// <param name="sourceType">The data source type. Category and file types are supported.</param> /// <param name="sinkType">The vector storage type of the knowledge base.</param> /// <returns>The response object from Alibaba Cloud Model Studio.</returns> /// <exception cref="Exception">An exception is thrown if an error occurs during the call.</exception> public AlibabaCloud.SDK.Bailian20231229.Models.CreateIndexResponse CreateIndex( AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string fileId, string name, string structureType, string sourceType, string sinkType) { var headers = new Dictionary<string, string>() { }; var createIndexRequest = new AlibabaCloud.SDK.Bailian20231229.Models.CreateIndexRequest { StructureType = structureType, Name = name, SourceType = sourceType, SinkType = sinkType, DocumentIds = new List<string> { fileId } }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.CreateIndexWithOptions(workspaceId, createIndexRequest, headers, runtime); } ``` ## Go ``` // CreateIndex creates (initializes) a knowledge base in Alibaba Cloud Model Studio. // // Parameters: // - client (bailian20231229.Client): The client. // - workspaceId (string): The workspace ID. // - fileId (string): The file ID. // - name (string): The name of the knowledge base. // - structureType (string): The data structure type of the knowledge base. // - sourceType (string): The data source type. Category and file types are supported. // - sinkType (string): The vector storage type of the knowledge base. // // Returns: // - *bailian20231229.CreateIndexResponse: The response from Alibaba Cloud Model Studio. // - error: The error message. func CreateIndex(client *bailian20231229.Client, workspaceId, fileId, name, structureType, sourceType, sinkType string) (_result *bailian20231229.CreateIndexResponse, _err error) { headers := make(map[string]*string) createIndexRequest := &bailian20231229.CreateIndexRequest{ StructureType: tea.String(structureType), Name: tea.String(name), SourceType: tea.String(sourceType), SinkType: tea.String(sinkType), DocumentIds: []*string{tea.String(fileId)}, } runtime := &util.RuntimeOptions{} return client.CreateIndexWithOptions(tea.String(workspaceId), createIndexRequest, headers, runtime) } ``` **Request example** ``` { "Name": "Alibaba Cloud Model Studio Phone Knowledge Base", "SinkType": "BUILT_IN", "SourceType": "DATA_CENTER_FILE", "StructureType": "unstructured", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx", "DocumentIds": [ "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx" ] } ``` **Response example** ``` { "Status": "200", "Message": "success", "RequestId": "87CB0999-F1BB-5290-8C79-A875B2XXXXXX", "Data": { "Id": "mymxbdxxxx" }, "Code": "Success", "Success": "true" } ``` |
| #### **3.2. Submit an index job** After initializing the knowledge base, call the [SubmitIndexJob](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-submitindexjob) operation to start the index building process. - **index\\_id:** Provide the `Data.Id` returned by the API when you [initialize the knowledge base](#00ded5ee90ffx). After the submission is complete, Model Studio immediately starts building the index as an asynchronous task. The `Data.Id` returned by this API call is the corresponding task ID. You will use this ID in the next step to query the latest status of the task. | **Important** - Before calling this operation, a [RAM user](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) must be granted the required API permissions (the AliyunBailianDataFullAccess policy). - This operation supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/SubmitIndexJob) and [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/SubmitIndexJob?lang=JAVA&tab=DEMO) for multiple languages. ## Python ``` def submit_index(client, workspace_id, index_id): """ Submit an index job to Alibaba Cloud Model Studio. Args: client (bailian20231229Client): The client. workspace_id (str): The workspace ID. index_id (str): The knowledge base ID. Returns: The response from Alibaba Cloud Model Studio. """ headers = {} submit_index_job_request = bailian_20231229_models.SubmitIndexJobRequest( index_id=index_id ) runtime = util_models.RuntimeOptions() return client.submit_index_job_with_options(workspace_id, submit_index_job_request, headers, runtime) ``` ## Java ``` /** * Submit an index job to Alibaba Cloud Model Studio. * * @param client The client object. * @param workspaceId The workspace ID. * @param indexId The knowledge base ID. * @return The response object from Alibaba Cloud Model Studio. */ public SubmitIndexJobResponse submitIndex(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId) throws Exception { Map<String, String> headers = new HashMap<>(); com.aliyun.bailian20231229.models.SubmitIndexJobRequest submitIndexJobRequest = new com.aliyun.bailian20231229.models.SubmitIndexJobRequest(); submitIndexJobRequest.setIndexId(indexId); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); return client.submitIndexJobWithOptions(workspaceId, submitIndexJobRequest, headers, runtime); } ``` ## PHP ``` /** * Submit an index job to Alibaba Cloud Model Studio. * * @param Bailian $client The client. * @param string $workspaceId The workspace ID. * @param string $indexId The knowledge base ID. * @return SubmitIndexJobResponse The response from Alibaba Cloud Model Studio. */ public static function submitIndex($client, $workspaceId, $indexId) { $headers = []; $submitIndexJobRequest = new SubmitIndexJobRequest([ 'indexId' => $indexId ]); $runtime = new RuntimeOptions([]); return $client->submitIndexJobWithOptions($workspaceId, $submitIndexJobRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Submit an index job. * @param {Bailian20231229Client} client - The client. * @param {string} workspaceId - The workspace ID. * @param {string} indexId - The knowledge base ID. * @returns {Promise<bailian20231229.SubmitIndexJobResponse>} - The response from Alibaba Cloud Model Studio. */ async function submitIndex(client, workspaceId, indexId) { const headers = {}; const req = new bailian20231229.SubmitIndexJobRequest({ indexId }); const runtime = new Util.RuntimeOptions({}); return await client.submitIndexJobWithOptions(workspaceId, req, headers, runtime); } ``` ## C# ``` /// <summary> /// Submit an index job to Alibaba Cloud Model Studio. /// </summary> /// <param name="client">The client object.</param> /// <param name="workspaceId">The workspace ID.</param> /// <param name="indexId">The knowledge base ID.</param> /// <returns>The response object from Alibaba Cloud Model Studio.</returns> /// <exception cref="Exception">An exception is thrown if an error occurs during the call.</exception> public AlibabaCloud.SDK.Bailian20231229.Models.SubmitIndexJobResponse SubmitIndex( AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string indexId) { var headers = new Dictionary<string, string>() { }; var submitIndexJobRequest = new AlibabaCloud.SDK.Bailian20231229.Models.SubmitIndexJobRequest { IndexId = indexId }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.SubmitIndexJobWithOptions(workspaceId, submitIndexJobRequest, headers, runtime); } ``` ## Go ``` // SubmitIndex submits an index job. // // Parameters: // - client (bailian20231229.Client): The client. // - workspaceId (string): The workspace ID. // - indexId (string): The knowledge base ID. // // Returns: // - *bailian20231229.SubmitIndexJobResponse: The response from Alibaba Cloud Model Studio. // - error: The error message. func SubmitIndex(client *bailian20231229.Client, workspaceId, indexId string) (_result *bailian20231229.SubmitIndexJobResponse, _err error) { headers := make(map[string]*string) submitIndexJobRequest := &bailian20231229.SubmitIndexJobRequest{ IndexId: tea.String(indexId), } runtime := &util.RuntimeOptions{} return client.SubmitIndexJobWithOptions(tea.String(workspaceId), submitIndexJobRequest, headers, runtime) } ``` **Request example** ``` { "IndexId": "mymxbdxxxx", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx" } ``` **Response example** ``` { "Status": "200", "Message": "success", "RequestId": "7774575F-571D-5854-82C2-634AB8XXXXXX", "Data": { "IndexId": "mymxbdxxxx", "Id": "3cd6fb57aaf44cd0b4dd2ca584xxxxxx" }, "Code": "Success", "Success": "true" } ``` |
| #### **3.3. Query index job status** The index job takes some time to complete. During peak hours, this process can take several hours. Call the [GetIndexJobStatus](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-getindexjobstatus) operation to query its execution status. - **job\\_id:** Pass the `Data.Id` that is returned by the API when you [submit an index job](#bf14fb34a58vy). When the `Data.Status` field is `COMPLETED`, the knowledge base has been created. | **Important** - Before calling this operation, a [RAM user](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) must be granted the required API permissions (the AliyunBailianDataFullAccess policy). - This operation supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/SubmitIndexJob) and [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/SubmitIndexJob?lang=JAVA&tab=DEMO) for multiple languages. ## Python ``` def get_index_job_status(client, workspace_id, index_id, job_id): """ Query the status of an index job. Args: client (bailian20231229Client): The client. workspace_id (str): The workspace ID. index_id (str): The knowledge base ID. job_id (str): The job ID. Returns: The response from Alibaba Cloud Model Studio. """ headers = {} get_index_job_status_request = bailian_20231229_models.GetIndexJobStatusRequest( index_id=index_id, job_id=job_id ) runtime = util_models.RuntimeOptions() return client.get_index_job_status_with_options(workspace_id, get_index_job_status_request, headers, runtime) ``` ## Java ``` /** * Query the status of an index job. * * @param client The client object. * @param workspaceId The workspace ID. * @param jobId The job ID. * @param indexId The knowledge base ID. * @return The response object from Alibaba Cloud Model Studio. */ public GetIndexJobStatusResponse getIndexJobStatus(com.aliyun.bailian20231229.Client client, String workspaceId, String jobId, String indexId) throws Exception { Map<String, String> headers = new HashMap<>(); com.aliyun.bailian20231229.models.GetIndexJobStatusRequest getIndexJobStatusRequest = new com.aliyun.bailian20231229.models.GetIndexJobStatusRequest(); getIndexJobStatusRequest.setIndexId(indexId); getIndexJobStatusRequest.setJobId(jobId); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); GetIndexJobStatusResponse getIndexJobStatusResponse = null; getIndexJobStatusResponse = client.getIndexJobStatusWithOptions(workspaceId, getIndexJobStatusRequest, headers, runtime); return getIndexJobStatusResponse; } ``` ## PHP ``` /** * Query the status of an index job. * * @param Bailian $client The client. * @param string $workspaceId The workspace ID. * @param string $indexId The knowledge base ID. * @param string $jobId The job ID. * @return GetIndexJobStatusResponse The response from Alibaba Cloud Model Studio. */ public function getIndexJobStatus($client, $workspaceId, $jobId, $indexId) { $headers = []; $getIndexJobStatusRequest = new GetIndexJobStatusRequest([ 'indexId' => $indexId, 'jobId' => $jobId ]); $runtime = new RuntimeOptions([]); return $client->getIndexJobStatusWithOptions($workspaceId, $getIndexJobStatusRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Query the status of an index job. * @param {Bailian20231229Client} client - The client. * @param {string} workspaceId - The workspace ID. * @param {string} jobId - The job ID. * @param {string} indexId - The knowledge base ID. * @returns {Promise<bailian20231229.GetIndexJobStatusResponse>} - The response from Alibaba Cloud Model Studio. */ async function getIndexJobStatus(client, workspaceId, jobId, indexId) { const headers = {}; const req = new bailian20231229.GetIndexJobStatusRequest({ jobId, indexId }); const runtime = new Util.RuntimeOptions({}); return await client.getIndexJobStatusWithOptions(workspaceId, req, headers, runtime); } ``` ## C# ``` /// <summary> /// Query the status of an index job. /// </summary> /// <param name="client">The client object.</param> /// <param name="workspaceId">The workspace ID.</param> /// <param name="jobId">The job ID.</param> /// <param name="indexId">The knowledge base ID.</param> /// <returns>The response object from Alibaba Cloud Model Studio.</returns> /// <exception cref="Exception">An exception is thrown if an error occurs during the call.</exception> public AlibabaCloud.SDK.Bailian20231229.Models.GetIndexJobStatusResponse GetIndexJobStatus( AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string jobId, string indexId) { var headers = new Dictionary<string, string>() { }; var getIndexJobStatusRequest = new AlibabaCloud.SDK.Bailian20231229.Models.GetIndexJobStatusRequest { IndexId = indexId, JobId = jobId }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.GetIndexJobStatusWithOptions(workspaceId, getIndexJobStatusRequest, headers, runtime); } ``` ## Go ``` // GetIndexJobStatus queries the status of an index job. // // Parameters: // - client (bailian20231229.Client): The client. // - workspaceId (string): The workspace ID. // - jobId (string): The job ID. // - indexId (string): The knowledge base ID. // // Returns: // - *bailian20231229.GetIndexJobStatusResponse: The response from Alibaba Cloud Model Studio. // - error: The error message. func GetIndexJobStatus(client *bailian20231229.Client, workspaceId, jobId, indexId string) (_result *bailian20231229.GetIndexJobStatusResponse, _err error) { headers := make(map[string]*string) getIndexJobStatusRequest := &bailian20231229.GetIndexJobStatusRequest{ JobId: tea.String(jobId), IndexId: tea.String(indexId), } runtime := &util.RuntimeOptions{} return client.GetIndexJobStatusWithOptions(tea.String(workspaceId), getIndexJobStatusRequest, headers, runtime) } ``` **Request example** ``` { "IndexId": "mymxbdxxxx", "JobId": "3cd6fb57aaf44cd0b4dd2ca584xxxxxx", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx" } ``` **Response example** ``` { "Status": "200", "Message": "success", "RequestId": "E83423B9-7D6D-5283-836B-CF7EAEXXXXXX", "Data": { "Status": "COMPLETED", "Documents": [ { "Status": "FINISH", "DocId": "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx", "Message": "Imported successfully.", "DocName": "Alibaba Cloud Model Studio Product Overview", "Code": "FINISH" } ], "JobId": "3cd6fb57aaf44cd0b4dd2ca584xxxxxx" }, "Code": "Success", "Success": "true" } ``` |

You have created a knowledge base from the uploaded files.

## **Retrieve from a knowledge base**

You can retrieve information from a knowledge base in two ways:

-   **Using an Alibaba Cloud Model Studio application:** When you [call an application](https://help.aliyun.com/en/model-studio/application-calling-guide#4100253b7chc3), use the `rag_options` parameter to pass the knowledge base ID `index_id`. This supplements your model with private knowledge and provides the latest information.
    
-   **Using an Alibaba Cloud API:** Call the [Retrieve API](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-retrieve) to retrieve information from a specified knowledge base and return the original text segments.
    

The first method sends the retrieved text segments to your configured model to generate a final answer, while the second method directly returns the text segments.

This section covers how to **use an Alibaba Cloud API**.

| To retrieve information and return text segments from a specified knowledge base, call the [Retrieve API](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-retrieve). - **client:** [How to obtain the client](#52ff2774f0pq9) - **workspace\\_id:** The ID of the workspace that contains the knowledge base. [How to obtain the workspace ID](https://help.aliyun.com/en/model-studio/use-workspace#c5222ec081sbo) > A RAM user can only retrieve information from a knowledge base in a [workspace they have joined](https://help.aliyun.com/en/model-studio/grant-the-business-space-permission-to-ram-users). If a response contains excessive irrelevant information, specify [SearchFilters](https://help.aliyun.com/en/model-studio/how-to-use-search-filters) in the request to filter results by criteria such as [tags](https://help.aliyun.com/en/model-studio/rag-knowledge-base#0a4efa5d7dta6). | **Important** - A RAM user must have the required [API permissions](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) (the AliyunBailianDataFullAccess policy) to call this operation. - This operation supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/Retrieve) and [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/Retrieve?lang=JAVA&tab=DEMO) for multiple languages. ## Python ``` def retrieve_index(client, workspace_id, index_id, query): """ Retrieves information from a specified knowledge base. Args: client (bailian20231229Client): The client object. workspace_id (str): The workspace ID. index_id (str): The knowledge base ID. query (str): The search query. Returns: The response from the Model Studio service. """ headers = {} retrieve_request = bailian_20231229_models.RetrieveRequest( index_id=index_id, query=query ) runtime = util_models.RuntimeOptions() return client.retrieve_with_options(workspace_id, retrieve_request, headers, runtime) ``` ## Java ``` /** * Retrieves information from a specified knowledge base. * * @param client The client object. * @param workspaceId The workspace ID. * @param indexId The knowledge base ID. * @param query The search query. * @return The response from the Model Studio service. */ public RetrieveResponse retrieveIndex(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId, String query) throws Exception { RetrieveRequest retrieveRequest = new RetrieveRequest(); retrieveRequest.setIndexId(indexId); retrieveRequest.setQuery(query); RuntimeOptions runtime = new RuntimeOptions(); return client.retrieveWithOptions(workspaceId, retrieveRequest, null, runtime); } ``` ## PHP ``` /** * Retrieves information from a specified knowledge base. * * @param Bailian $client The client object. * @param string $workspaceId The workspace ID. * @param string $indexId The knowledge base ID. * @param string $query The search query. * @return RetrieveResponse The response from the Model Studio service. * @throws Exception */ public function retrieveIndex($client, $workspaceId, $indexId, $query) { $headers = []; $retrieveRequest = new RetrieveRequest([ "query" => $query, "indexId" => $indexId ]); $runtime = new RuntimeOptions([]); return $client->retrieveWithOptions($workspaceId, $retrieveRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Retrieves information from a specified knowledge base. * @param {bailian20231229.Client} client The client object. * @param {string} workspaceId The workspace ID. * @param {string} indexId The knowledge base ID. * @param {string} query The search query. * @returns {Promise<bailian20231229.RetrieveResponse>} The response from the Model Studio service. */ async function retrieveIndex(client, workspaceId, indexId, query) { const headers = {}; const req = new bailian20231229.RetrieveRequest({ indexId, query }); const runtime = new Util.RuntimeOptions({}); return await client.retrieveWithOptions(workspaceId, req, headers, runtime); } ``` ## C# ``` /// <summary> /// Retrieves information from a specified knowledge base. /// </summary> /// <param name="client">The client object.</param> /// <param name="workspaceId">The workspace ID.</param> /// <param name="indexId">The knowledge base ID.</param> /// <param name="query">The search query.</param> /// <returns>The response from the Model Studio service.</returns> /// <exception cref="Exception">Thrown if the call fails.</exception> public AlibabaCloud.SDK.Bailian20231229.Models.RetrieveResponse RetrieveIndex( AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string indexId, string query) { var headers = new Dictionary<string, string>() { }; var retrieveRequest = new AlibabaCloud.SDK.Bailian20231229.Models.RetrieveRequest { IndexId = indexId, Query = query }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.RetrieveWithOptions(workspaceId, retrieveRequest, headers, runtime); } ``` ## Go ``` // retrieveIndex retrieves information from a specified knowledge base. // // Args: // - client (bailian20231229.Client): The client object. // - workspaceId (string): The workspace ID. // - indexId (string): The knowledge base ID. // - query (string): The search query. // // Returns: // - *bailian20231229.RetrieveResponse: The response from the Model Studio service. // - error: The error, if any. func retrieveIndex(client *bailian20231229.Client, workspaceId, indexId, query string) (*bailian20231229.RetrieveResponse, error) { headers := make(map[string]*string) request := &bailian20231229.RetrieveRequest{ IndexId: tea.String(indexId), Query: tea.String(query), } runtime := &util.RuntimeOptions{} return client.RetrieveWithOptions(tea.String(workspaceId), request, headers, runtime) } ``` **Sample request** ``` { "IndexId": "mymxbdxxxx", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx", "Query": "Please introduce the Alibaba Cloud Model Studio X1 phone." } ``` **Sample response** ``` { "Status": "200", "Message": "success", "RequestId": "17316EA2-1F4D-55AC-8872-53F6F1XXXXXX", "Data": { "Nodes": [ { "Score": 0.6294550895690918, "Metadata": { "file_path": "https://bailian-datahub-data-prod.oss-cn-beijing.aliyuncs.com/10285263/multimodal/docJson/Model_Studio_Series_Phone_Product_Introduction_1742197778230.json?Expires=1742457465&OSSAccessKeyId=TestID&Signature=ptFkSObdnBrbJNEw8CnlOSP%2FTeI%3D", "is_displayed_chunk_content": "true", "_rc_v_score": 0.7449869735535081, "image_url": [], "nid": "9ad347d9e4d7465d2c1e693a08b0077c\\|d6f7fbf8403e0df796258e5ada1ee1c1\\|4772257e93ed64ea087ff4be0d5e4620\\|7ce1370e4a1958842c9268144a452cc7", "_q_score": 1, "source": "0", "_score": 0.6294550895690918, "title": "Alibaba Cloud Model Studio Phone Product Introduction", "doc_id": "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx", "content": "Alibaba Cloud Model Studio Phone Product Introduction\\nAlibaba Cloud Model Studio X1 — Enjoy the ultimate visual experience: Features a 6.7-inch 1440 x 3200 pixel ultra-clear screen with a 120 Hz refresh rate for a smooth and vivid visual experience. The powerful combination of 256 GB of mass storage and 12 GB of RAM handles large games and multitasking with ease. A long-lasting 5000 mAh battery and an ultra-sensitive quad-camera system capture every wonderful moment of your life. Reference price: 4,599–4,999\\nTongyi Vivid 7 — A new experience in smart photography: Features a 6.5-inch 1080 x 2400 pixel full screen. The AI smart photography feature ensures every photo shows professional-grade color and detail. 8 GB of RAM and 128 GB of storage ensure smooth operation, and the 4,500 mAh battery meets daily needs. Side fingerprint unlock is convenient and secure. Reference price: 2,999–3,299\\nStardust S9 Pro — An innovative visual feast: A groundbreaking 6.9-inch 1440 x 3088 pixel under-screen camera design provides a borderless visual experience. Top-tier configuration with 512 GB of storage and 16 GB of RAM, combined with a 6,000 mAh battery and 100 W fast charging technology, delivers both performance and endurance, leading the tech trend. Reference price: 5,999–6,499.", "_rc_score": 0, "workspace_id": "llm-4u5xpd1xdjqpxxxx", "hier_title": "Alibaba Cloud Model Studio Phone Product Introduction", "_rc_t_score": 0.05215025693178177, "doc_name": "Alibaba Cloud Model Studio Series Phone Product Introduction", "pipeline_id": "mymxbdxxxx", "_id": "llm-4u5xpd1xdjqp8itj_mymxbd6172_file_0b21e0a852cd40cd9741c54fefbb61cd_10285263_0_0" }, "Text": "Alibaba Cloud Model Studio Phone Product Introduction\\nAlibaba Cloud Model Studio X1 — Enjoy the ultimate visual experience: Features a 6.7-inch 1440 x 3200 pixel ultra-clear screen with a 120 Hz refresh rate for a smooth and vivid visual experience. The powerful combination of 256 GB of mass storage and 12 GB of RAM handles large games and multitasking with ease. A long-lasting 5000 mAh battery and an ultra-sensitive quad-camera system capture every wonderful moment of your life. Reference price: 4,599–4,999\\nTongyi Vivid 7 — A new experience in smart photography: Features a 6.5-inch 1080 x 2400 pixel full screen. The AI smart photography feature ensures every photo shows professional-grade color and detail. 8 GB of RAM and 128 GB of storage ensure smooth operation, and the 4,500 mAh battery meets daily needs. Side fingerprint unlock is convenient and secure. Reference price: 2,999–3,299\\nStardust S9 Pro — An innovative visual feast: A groundbreaking 6.9-inch 1440 x 3088 pixel under-screen camera design provides a borderless visual experience. Top-tier configuration with 512 GB of storage and 16 GB of RAM, combined with a 6,000 mAh battery and 100 W fast charging technology, delivers both performance and endurance, leading the tech trend. Reference price: 5,999–6,499." }, { "Score": 0.5322970747947693, "Metadata": { "file_path": "https://bailian-datahub-data-prod.oss-cn-beijing.aliyuncs.com/10285263/multimodal/docJson/Model_Studio_Series_Phone_Product_Introduction_1742197778230.json?Expires=1742457465&OSSAccessKeyId=TestID&Signature=ptFkSObdnBrbJNEw8CnlOSP%2FTeI%3D", "is_displayed_chunk_content": "true", "_rc_v_score": 0.641660213470459, "image_url": [], "nid": "00be1864c18b4c39c59f83713af80092\\|4f2bfb02cc9fc4e85597b2e717699207", "_q_score": 0.9948930557644994, "source": "0", "_score": 0.5322970747947693, "title": "Alibaba Cloud Model Studio Phone Product Introduction", "doc_id": "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx", "content": "Alibaba Cloud Model Studio Flex Fold+ — A new era of foldable screens: Combining innovation and luxury, it features a 7.6-inch 1800 x 2400 pixel main screen and a 4.7-inch 1080 x 2400 pixel external screen. The multi-angle free-stop hinge design meets the needs of different scenarios. Alibaba Cloud Model Studio Flex Fold+ — A new era of foldable screens: Combining innovation and luxury, it features a 7.6-inch 1800 x 2400 pixel main screen and a 4.7-inch 1080 x 2400 pixel external screen. The multi-angle free-stop hinge design meets the needs of different scenarios. 512 GB of storage, 12 GB of RAM, a 4700 mAh battery, and UTG ultra-thin flexible glass open a new chapter in the era of foldable screens. In addition, this phone supports Dual SIM Dual Standby and satellite calls, helping you stay connected anywhere in the world. Reference retail price: 9,999–10,999. Each phone is a masterpiece of craftsmanship, designed to be a work of technological art in your hands. Choose your smart companion and start a new chapter of future tech life.", "_rc_score": 0, "workspace_id": "llm-4u5xpd1xdjqpxxxx", "hier_title": "Alibaba Cloud Model Studio Phone Product Introduction", "_rc_t_score": 0.05188392847776413, "doc_name": "Alibaba Cloud Model Studio Series Phone Product Introduction", "pipeline_id": "mymxbdxxxx", "_id": "llm-4u5xpd1xdjqp8itj_mymxbd6172_file_0b21e0a852cd40cd9741c54fefbb61cd_10285263_0_2" }, "Text": "Alibaba Cloud Model Studio Flex Fold+ — A new era of foldable screens: Combining innovation and luxury, it features a 7.6-inch 1800 x 2400 pixel main screen and a 4.7-inch 1080 x 2400 pixel external screen. The multi-angle free-stop hinge design meets the needs of different scenarios. Alibaba Cloud Model Studio Flex Fold+ — A new era of foldable screens: Combining innovation and luxury, it features a 7.6-inch 1800 x 2400 pixel main screen and a 4.7-inch 1080 x 2400 pixel external screen. The multi-angle free-stop hinge design meets the needs of different scenarios. 512 GB of storage, 12 GB of RAM, a 4700 mAh battery, and UTG ultra-thin flexible glass open a new chapter in the era of foldable screens. In addition, this phone supports Dual SIM Dual Standby and satellite calls, helping you stay connected anywhere in the world. Reference retail price: 9,999–10,999. Each phone is a masterpiece of craftsmanship, designed to be a work of technological art in your hands. Choose your smart companion and start a new chapter of future tech life." }, { "Score": 0.5050643086433411, "Metadata": { "file_path": "https://bailian-datahub-data-prod.oss-cn-beijing.aliyuncs.com/10285263/multimodal/docJson/Model_Studio_Series_Phone_Product_Introduction_1742197778230.json?Expires=1742457465&OSSAccessKeyId=TestID&Signature=ptFkSObdnBrbJNEw8CnlOSP%2FTeI%3D", "is_displayed_chunk_content": "true", "_rc_v_score": 0.6757396459579468, "image_url": [], "nid": "f05d1b51eb6b033b32a162d90a9da71b\\|5cb6b848be8d11eb168c031025415cc5\\|4f2bfb02cc9fc4e85597b2e717699207", "_q_score": 0.9890713450653327, "source": "0", "_score": 0.5050643086433411, "title": "Alibaba Cloud Model Studio Phone Product Introduction", "doc_id": "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx", "content": "Top-tier configuration with 512 GB of storage and 16 GB of RAM, combined with a 6,000 mAh battery and 100 W fast charging technology, delivers both performance and endurance, leading the tech trend. Reference price: 5,999–6,499. Alibaba Cloud Model Studio Ace Ultra — The gamer's choice: Equipped with a 6.67-inch 1080 x 2400 pixel screen, 10 GB of RAM, and 256 GB of storage to ensure silky-smooth gameplay. The 5,500 mAh battery with a liquid cooling system stays cool even during long gaming sessions. High-dynamic dual speakers upgrade the gaming experience with immersive sound effects. Reference price: 3,999–4,299. Alibaba Cloud Model Studio Zephyr Z9 — The art of being thin and portable: A lightweight 6.4-inch 1080 x 2340 pixel design, with 128 GB of storage and 6 GB of RAM, is more than enough for daily use. The 4,000 mAh battery ensures a full day of use without worry. The 30x digital zoom lens captures distant details. It is thin but powerful. Reference price: 2,499–2,799. Alibaba Cloud Model Studio Flex Fold+ — A new era of foldable screens: Combining innovation and luxury, it features a 7.6-inch 1800 x 2400 pixel main screen and a 4.7-inch 1080 x 2400 pixel external screen. The multi-angle free-stop hinge design meets the needs of different scenarios.", "_rc_score": 0, "workspace_id": "llm-4u5xpd1xdjqpxxxx", "hier_title": "Alibaba Cloud Model Studio Phone Product Introduction", "_rc_t_score": 0.05158032476902008, "doc_name": "Alibaba Cloud Model Studio Series Phone Product Introduction", "pipeline_id": "mymxbdxxxx", "_id": "llm-4u5xpd1xdjqp8itj_mymxbd6172_file_0b21e0a852cd40cd9741c54fefbb61cd_10285263_0_1" }, "Text": "Top-tier configuration with 512 GB of storage and 16 GB of RAM, combined with a 6,000 mAh battery and 100 W fast charging technology, delivers both performance and endurance, leading the tech trend. Reference price: 5,999–6,499. Alibaba Cloud Model Studio Ace Ultra — The gamer's choice: Equipped with a 6.67-inch 1080 x 2400 pixel screen, 10 GB of RAM, and 256 GB of storage to ensure silky-smooth gameplay. The 5,500 mAh battery with a liquid cooling system stays cool even during long gaming sessions. High-dynamic dual speakers upgrade the gaming experience with immersive sound effects. Reference price: 3,999–4,299. Alibaba Cloud Model Studio Zephyr Z9 — The art of being thin and portable: A lightweight 6.4-inch 1080 x 2340 pixel design, with 128 GB of storage and 6 GB of RAM, is more than enough for daily use. The 4,000 mAh battery ensures a full day of use without worry. The 30x digital zoom lens captures distant details. It is thin but powerful. Reference price: 2,499–2,799. Alibaba Cloud Model Studio Flex Fold+ — A new era of foldable screens: Combining innovation and luxury, it features a 7.6-inch 1800 x 2400 pixel main screen and a 4.7-inch 1080 x 2400 pixel external screen. The multi-angle free-stop hinge design meets the needs of different scenarios." } ] }, "Code": "Success", "Success": "true" } ``` |
| --- | --- | --- | --- | --- | --- | --- | --- |

## **Update a knowledge base**

The following example shows how to update a document search knowledge base. Applications that use the knowledge base reflect your updates in real time. New content becomes available for retrieval, while deleted content is no longer accessible.

> You cannot update data query or image Q&A knowledge bases using an API. For more information, see [Update a knowledge base](https://help.aliyun.com/en/model-studio/rag-knowledge-base#b2f92e9d2car8).

-   **Incremental update:** The only supported method is a three-step process: upload the updated file, append the file to the knowledge base, and then delete the old file.
    
-   **Full update:** For each file in the knowledge base, perform the three steps to complete the update.
    
-   **Automatic update or synchronization:** For more information, see [How to automatically update or synchronize a knowledge base](#827f8c570a9ni).
    
-   **File limit for a single update:** We recommend updating no more than 100,000 files at a time. Exceeding this limit might prevent the knowledge base from updating correctly.
    

| ### **1\\. Upload the updated file** Follow the procedure in [Create a knowledge base: Step 2](#4b4a1236aalno) to upload the updated file to the workspace that contains the knowledge base. > Request a new file upload lease to generate a new set of upload parameters for the updated file. |     |
| --- | --- |
| ### **2\\. Append file to the knowledge base** |   |
| #### **2.1. Submit an append task** After the uploaded file is parsed, call the [SubmitIndexAddDocumentsJob](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-submitindexadddocumentsjob) operation to append the new file to the knowledge base and rebuild the knowledge base index. - **client:** For more information, see [How to obtain the client](#52ff2774f0pq9). - **workspace\\_id:** For more information, see [How to obtain a workspace ID](https://help.aliyun.com/en/model-studio/use-workspace#c5222ec081sbo). - **file\\_id:** Enter the `FileId` that is returned when you [add a file to a category](#494345d4b1hx2). - **source\\_type:** In this example, enter `DATA_CENTER_FILE`. After you submit the task, Model Studio rebuilds the knowledge base asynchronously. This operation returns `Data.Id`, which is the task ID (job\\_id). Use this ID in the next step to query the task status. **Important** - After you call the SubmitIndexAddDocumentsJob operation, the task takes some time to complete. You can use the `job_id` to query the task status. **Do not resubmit the task before it is complete.** | **Important** - A RAM user must be granted the required [API permissions](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) (the AliyunBailianDataFullAccess policy) before calling this operation. - This example supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/SubmitIndexAddDocumentsJob) and multi-language [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/SubmitIndexAddDocumentsJob?lang=JAVA&tab=DEMO). ## Python ``` def submit_index_add_documents_job(client, workspace_id, index_id, file_id, source_type): """ Appends and imports a parsed file to a document search knowledge base. Args: client (bailian20231229Client): The client. workspace_id (str): The workspace ID. index_id (str): The knowledge base ID. file_id (str): The file ID. source_type(str): The data type. Returns: The response from the Alibaba Cloud Model Studio service. """ headers = {} submit_index_add_documents_job_request = bailian_20231229_models.SubmitIndexAddDocumentsJobRequest( index_id=index_id, document_ids=[file_id], source_type=source_type ) runtime = util_models.RuntimeOptions() return client.submit_index_add_documents_job_with_options(workspace_id, submit_index_add_documents_job_request, headers, runtime) ``` ## Java ``` /** * Appends and imports a parsed file to a document search knowledge base. * * @param client The client. * @param workspaceId The workspace ID. * @param indexId The knowledge base ID. * @param fileId The file ID. * @param sourceType The data type. * @return The response from the Alibaba Cloud Model Studio service. */ public SubmitIndexAddDocumentsJobResponse submitIndexAddDocumentsJob(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId, String fileId, String sourceType) throws Exception { Map<String, String> headers = new HashMap<>(); SubmitIndexAddDocumentsJobRequest submitIndexAddDocumentsJobRequest = new SubmitIndexAddDocumentsJobRequest(); submitIndexAddDocumentsJobRequest.setIndexId(indexId); submitIndexAddDocumentsJobRequest.setDocumentIds(Collections.singletonList(fileId)); submitIndexAddDocumentsJobRequest.setSourceType(sourceType); RuntimeOptions runtime = new RuntimeOptions(); return client.submitIndexAddDocumentsJobWithOptions(workspaceId, submitIndexAddDocumentsJobRequest, headers, runtime); } ``` ## PHP ``` /** * Appends and imports a parsed file to a document search knowledge base. * * @param Bailian $client The client object. * @param string $workspaceId The workspace ID. * @param string $indexId The knowledge base ID. * @param string $fileId The file ID. * @param string $sourceType The data type. * @return SubmitIndexAddDocumentsJobResponse The response from the Alibaba Cloud Model Studio service. * @throws Exception */ public function submitIndexAddDocumentsJob($client, $workspaceId, $indexId, $fileId, $sourceType) { $headers = []; $submitIndexAddDocumentsJobRequest = new SubmitIndexAddDocumentsJobRequest([ "indexId" =>$indexId, "sourceType" => $sourceType, "documentIds" => [ $fileId ] ]); $runtime = new RuntimeOptions([]); return $client->submitIndexAddDocumentsJobWithOptions($workspaceId, $submitIndexAddDocumentsJobRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Submits a task to append a file. * @param {Bailian20231229Client} client - The client. * @param {string} workspaceId - The workspace ID. * @param {string} indexId - The knowledge base ID. * @param {string} fileId - The file ID. * @param {string} sourceType - The data type. * @returns {Promise<bailian20231229.SubmitIndexAddDocumentsJobResponse>} - The response from the Alibaba Cloud Model Studio service. */ async function submitIndexAddDocumentsJob(client, workspaceId, indexId, fileId, sourceType) { const headers = {}; const req = new bailian20231229.SubmitIndexAddDocumentsJobRequest({ indexId, documentIds: [fileId], sourceType, }); const runtime = new Util.RuntimeOptions({}); return await client.submitIndexAddDocumentsJobWithOptions(workspaceId, req, headers, runtime); } ``` ## C# ``` /// <summary> /// Appends and imports a parsed file to a document search knowledge base. /// </summary> /// <param name="client">The client.</param> /// <param name="workspaceId">The workspace ID.</param> /// <param name="indexId">The knowledge base ID.</param> /// <param name="fileId">The file ID.</param> /// <param name="sourceType">The data type.</param> /// <returns>The response from the Alibaba Cloud Model Studio service.</returns> public AlibabaCloud.SDK.Bailian20231229.Models.SubmitIndexAddDocumentsJobResponse SubmitIndexAddDocumentsJob( AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string indexId, string fileId, string sourceType) { var headers = new Dictionary<string, string>() { }; var submitIndexAddDocumentsJobRequest = new AlibabaCloud.SDK.Bailian20231229.Models.SubmitIndexAddDocumentsJobRequest { IndexId = indexId, DocumentIds = new List<string> { fileId }, SourceType = sourceType }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.SubmitIndexAddDocumentsJobWithOptions(workspaceId, submitIndexAddDocumentsJobRequest, headers, runtime); } ``` ## Go ``` // SubmitIndexAddDocumentsJob appends and imports a parsed file to a document search knowledge base. // // Parameters: // - client (bailian20231229.Client): The client. // - workspaceId (string): The workspace ID. // - indexId (string): The knowledge base ID. // - fileId(string): The file ID. // - sourceType(string): The data type. // // Returns: // - *bailian20231229.SubmitIndexAddDocumentsJobResponse: The response from the Alibaba Cloud Model Studio service. // - error: The error message. func SubmitIndexAddDocumentsJob(client *bailian20231229.Client, workspaceId, indexId, fileId, sourceType string) (_result *bailian20231229.SubmitIndexAddDocumentsJobResponse, _err error) { headers := make(map[string]*string) submitIndexAddDocumentsJobRequest := &bailian20231229.SubmitIndexAddDocumentsJobRequest{ IndexId: tea.String(indexId), SourceType: tea.String(sourceType), DocumentIds: []*string{tea.String(fileId)}, } runtime := &util.RuntimeOptions{} return client.SubmitIndexAddDocumentsJobWithOptions(tea.String(workspaceId), submitIndexAddDocumentsJobRequest, headers, runtime) } ``` **Request example** ``` { "IndexId": "mymxbdxxxx", "SourceType": "DATA_CENTER_FILE", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx", "DocumentIds": [ "file_247a2fd456a349ee87d071404840109b_10xxxxxx" ] } ``` **Response example** ``` { "Status": "200", "RequestId": "F693EB60-FEFC-559A-BF56-A41F52XXXXXX", "Message": "success", "Data": { "Id": "d8d189a36a3248438dca23c078xxxxxx" }, "Code": "Success", "Success": "true" } ``` |
| #### **2.2. Wait for task completion** The indexing task takes some time to complete. During peak hours, this process can take several hours. You can call the [GetIndexJobStatus](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-getindexjobstatus) operation to query its execution status. - **job\\_id:** Enter the `Data.Id` that is returned when you [submit the task to append the file](#b2f19a956bcsl). A value of `COMPLETED` for the `Data.Status` field in the response indicates that all updated files have been successfully appended to the knowledge base. > The `Documents` list in the response contains all files for the append task corresponding to the `job_id` you provided. | **Important** - A RAM user must be granted the required [API permissions](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) (the AliyunBailianDataFullAccess policy) before calling this operation. - This example supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/GetIndexJobStatus) and multi-language [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/GetIndexJobStatus?lang=JAVA&tab=DEMO). ## Python ``` def get_index_job_status(client, workspace_id, index_id, job_id): """ Queries the status of an indexing task. Args: client (bailian20231229Client): The client. workspace_id (str): The workspace ID. index_id (str): The knowledge base ID. job_id (str): The task ID. Returns: The response from the Alibaba Cloud Model Studio service. """ headers = {} get_index_job_status_request = bailian_20231229_models.GetIndexJobStatusRequest( index_id=index_id, job_id=job_id ) runtime = util_models.RuntimeOptions() return client.get_index_job_status_with_options(workspace_id, get_index_job_status_request, headers, runtime) ``` ## Java ``` /** * Queries the status of an indexing task. * * @param client The client. * @param workspaceId The workspace ID. * @param jobId The task ID. * @param indexId The knowledge base ID. * @return The response from the Alibaba Cloud Model Studio service. */ public GetIndexJobStatusResponse getIndexJobStatus(com.aliyun.bailian20231229.Client client, String workspaceId, String jobId, String indexId) throws Exception { Map<String, String> headers = new HashMap<>(); com.aliyun.bailian20231229.models.GetIndexJobStatusRequest getIndexJobStatusRequest = new com.aliyun.bailian20231229.models.GetIndexJobStatusRequest(); getIndexJobStatusRequest.setIndexId(indexId); getIndexJobStatusRequest.setJobId(jobId); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); GetIndexJobStatusResponse getIndexJobStatusResponse = null; getIndexJobStatusResponse = client.getIndexJobStatusWithOptions(workspaceId, getIndexJobStatusRequest, headers, runtime); return getIndexJobStatusResponse; } ``` ## PHP ``` /** * Queries the status of an indexing task. * * @param Bailian $client The client. * @param string $workspaceId The workspace ID. * @param string $indexId The knowledge base ID. * @param string $jobId The task ID. * @return GetIndexJobStatusResponse The response from the Alibaba Cloud Model Studio service. */ public function getIndexJobStatus($client, $workspaceId, $jobId, $indexId) { $headers = []; $getIndexJobStatusRequest = new GetIndexJobStatusRequest([ 'indexId' => $indexId, 'jobId' => $jobId ]); $runtime = new RuntimeOptions([]); return $client->getIndexJobStatusWithOptions($workspaceId, $getIndexJobStatusRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Queries the status of an indexing task. * @param {Bailian20231229Client} client - The client. * @param {string} workspaceId - The workspace ID. * @param {string} jobId - The task ID. * @param {string} indexId - The knowledge base ID. * @returns {Promise<bailian20231229.GetIndexJobStatusResponse>} - The response from the Alibaba Cloud Model Studio service. */ static getIndexJobStatus(client, workspaceId, jobId, indexId) { const headers = {}; const req = new bailian20231229.GetIndexJobStatusRequest({ jobId, indexId }); const runtime = new Util.RuntimeOptions({}); return await client.getIndexJobStatusWithOptions(workspaceId, req, headers, runtime); } ``` ## C# ``` /// <summary> /// Queries the status of an indexing task. /// </summary> /// <param name="client">The client.</param> /// <param name="workspaceId">The workspace ID.</param> /// <param name="jobId">The task ID.</param> /// <param name="indexId">The knowledge base ID.</param> /// <returns>The response from the Alibaba Cloud Model Studio service.</returns> /// <exception cref="Exception">An exception is thrown if an error occurs during the call.</exception> public AlibabaCloud.SDK.Bailian20231229.Models.GetIndexJobStatusResponse GetIndexJobStatus( AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string jobId, string indexId) { var headers = new Dictionary<string, string>() { }; var getIndexJobStatusRequest = new AlibabaCloud.SDK.Bailian20231229.Models.GetIndexJobStatusRequest { IndexId = indexId, JobId = jobId }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.GetIndexJobStatusWithOptions(workspaceId, getIndexJobStatusRequest, headers, runtime); } ``` ## Go ``` // GetIndexJobStatus queries the status of an indexing task. // // Parameters: // - client (bailian20231229.Client): The client. // - workspaceId (string): The workspace ID. // - jobId (string): The task ID. // - indexId (string): The knowledge base ID. // // Returns: // - *bailian20231229.GetIndexJobStatusResponse: The response from the Alibaba Cloud Model Studio service. // - error: The error message. func GetIndexJobStatus(client *bailian20231229.Client, workspaceId, jobId, indexId string) (_result *bailian20231229.GetIndexJobStatusResponse, _err error) { headers := make(map[string]*string) getIndexJobStatusRequest := &bailian20231229.GetIndexJobStatusRequest{ JobId: tea.String(jobId), IndexId: tea.String(indexId), } runtime := &util.RuntimeOptions{} return client.GetIndexJobStatusWithOptions(tea.String(workspaceId), getIndexJobStatusRequest, headers, runtime) } ``` **Request example** ``` { "IndexId": "mymxbdxxxx", "JobId": "76f243b9ee534d59a61f156ff0xxxxxx", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx" } ``` **Response example** ``` { "Status": 200, "Message": "success", "RequestId": "7F727D58-D90E-51E7-B56E-985A42XXXXXX", "Data": { "Status": "COMPLETED", "Documents": [ { "Status": "FINISH", "DocId": "file_247a2fd456a349ee87d071404840109b_10xxxxxx", "Message": "Import successful", "DocName": "Alibaba Cloud Model Studio Phone Product Introduction", "Code": "FINISH" } ], "JobId": "76f243b9ee534d59a61f156ff0xxxxxx" }, "Code": "Success", "Success": true } ``` |
| ### **3\\. Delete the old file** Finally, call the [DeleteIndexDocument](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-deleteindexdocument) operation to permanently delete the old version of the file from the knowledge base. This prevents outdated information from being retrieved accidentally. - **file\\_id:** Enter the `FileId` of the old file. **Note** You can only delete files with a status of import failed (INSERT\\_ERROR) or import successful (FINISH). To query the status of files in the knowledge base, you can call the [ListIndexDocuments](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-listindexdocuments) operation. | **Important** - A RAM user must be granted the required [API permissions](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) (the AliyunBailianDataFullAccess policy) before calling this operation. - This example supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/DeleteIndexDocument) and multi-language [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/DeleteIndexDocument?lang=JAVA&tab=DEMO). ## Python ``` def delete_index_document(client, workspace_id, index_id, file_id): """ Permanently deletes one or more files from a specified document search knowledge base. Args: client (bailian20231229Client): The client. workspace_id (str): The workspace ID. index_id (str): The knowledge base ID. file_id (str): The file ID. Returns: The response from the Alibaba Cloud Model Studio service. """ headers = {} delete_index_document_request = bailian_20231229_models.DeleteIndexDocumentRequest( index_id=index_id, document_ids=[file_id] ) runtime = util_models.RuntimeOptions() return client.delete_index_document_with_options(workspace_id, delete_index_document_request, headers, runtime) ``` ## Java ``` /** * Permanently deletes one or more files from a specified document search knowledge base. * * @param client The client. * @param workspaceId The workspace ID. * @param indexId The knowledge base ID. * @param fileId The file ID. * @return The response from the Alibaba Cloud Model Studio service. */ public DeleteIndexDocumentResponse deleteIndexDocument(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId, String fileId) throws Exception { Map<String, String> headers = new HashMap<>(); DeleteIndexDocumentRequest deleteIndexDocumentRequest = new DeleteIndexDocumentRequest(); deleteIndexDocumentRequest.setIndexId(indexId); deleteIndexDocumentRequest.setDocumentIds(Collections.singletonList(fileId)); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); return client.deleteIndexDocumentWithOptions(workspaceId, deleteIndexDocumentRequest, headers, runtime); } ``` ## PHP ``` /** * Permanently deletes one or more files from a specified document search knowledge base. * * @param Bailian $client The client object. * @param string $workspaceId The workspace ID. * @param string $indexId The knowledge base ID. * @param string $fileId The file ID. * @return DeleteIndexDocumentResponse The response from the Alibaba Cloud Model Studio service. * @throws Exception */ public function deleteIndexDocument($client, $workspaceId, $indexId, $fileId) { $headers = []; $deleteIndexDocumentRequest = new DeleteIndexDocumentRequest([ "indexId" => $indexId, "documentIds" => [ $fileId ] ]); $runtime = new RuntimeOptions([]); return $client->deleteIndexDocumentWithOptions($workspaceId, $deleteIndexDocumentRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Permanently deletes one or more files from a specified document search knowledge base. * @param {Bailian20231229Client} client - The client. * @param {string} workspaceId - The workspace ID. * @param {string} indexId - The knowledge base ID. * @param {string} fileId - The file ID. * @returns {Promise<bailian20231229.DeleteIndexDocumentResponse>} - The response from the Alibaba Cloud Model Studio service. */ async function deleteIndexDocument(client, workspaceId, indexId, fileId) { const headers = {}; const req = new bailian20231229.DeleteIndexDocumentRequest({ indexId, documentIds: [fileId], }); const runtime = new Util.RuntimeOptions({}); return await client.deleteIndexDocumentWithOptions(workspaceId, req, headers, runtime); } ``` ## C# ``` /// <summary> /// Permanently deletes one or more files from a specified document search knowledge base. /// </summary> /// <param name="client">The client.</param> /// <param name="workspaceId">The workspace ID.</param> /// <param name="indexId">The knowledge base ID.</param> /// <param name="fileId">The file ID.</param> /// <returns>The response from the Alibaba Cloud Model Studio service.</returns> public AlibabaCloud.SDK.Bailian20231229.Models.DeleteIndexDocumentResponse DeleteIndexDocument( AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string indexId, string fileId) { var headers = new Dictionary<string, string>() { }; var deleteIndexDocumentRequest = new AlibabaCloud.SDK.Bailian20231229.Models.DeleteIndexDocumentRequest { IndexId = indexId, DocumentIds = new List<string> { fileId } }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.DeleteIndexDocumentWithOptions(workspaceId, deleteIndexDocumentRequest, headers, runtime); } ``` ## Go ``` // DeleteIndexDocument permanently deletes one or more files from a specified document search knowledge base. // // Parameters: // - client (bailian20231229.Client): The client. // - workspaceId (string): The workspace ID. // - indexId (string): The knowledge base ID. // - fileId (string): The file ID. // // Returns: // - *bailian20231229.DeleteIndexDocumentResponse: The response from the Alibaba Cloud Model Studio service. // - error: The error message. func DeleteIndexDocument(client *bailian20231229.Client, workspaceId, indexId, fileId string) (*bailian20231229.DeleteIndexDocumentResponse, error) { headers := make(map[string]*string) deleteIndexDocumentRequest := &bailian20231229.DeleteIndexDocumentRequest{ IndexId: tea.String(indexId), DocumentIds: []*string{tea.String(fileId)}, } runtime := &util.RuntimeOptions{} return client.DeleteIndexDocumentWithOptions(tea.String(workspaceId), deleteIndexDocumentRequest, headers, runtime) } ``` **Sample request** ``` { "DocumentIds": [ "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx" ], "IndexId": "mymxbdxxxx", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx" } ``` **Sample response** ``` { "Status": "200", "RequestId": "2D8505EC-C667-5102-9154-00B6FEXXXXXX", "Message": "success", "Data": { "DeletedDocument": [ "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx" ] }, "Code": "Success", "Success": "true" } ``` |

## **Manage knowledge bases**

> [Creating and using knowledge bases](https://help.aliyun.com/en/model-studio/rag-knowledge-base#81f57beb71zs1) are not supported through the API. You must perform these tasks in the [Model Studio console](https://bailian.console.aliyun.com/?&tab=app#/knowledge-base).

| ### **View a knowledge base** To view knowledge bases in a specified workspace, call the [ListIndices](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-listindices) operation. - **client:** [How to obtain the client](#52ff2774f0pq9) - **workspace\\_id:** [How to obtain the workspace ID](https://help.aliyun.com/en/model-studio/use-workspace#c5222ec081sbo) > A RAM user can view knowledge bases only in [workspaces they have joined](https://help.aliyun.com/en/model-studio/grant-the-business-space-permission-to-ram-users). | **Important** - Before calling this operation, a RAM user must have the required [API permissions](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) by attaching the AliyunBailianDataFullAccess policy. - This operation supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/ListIndices) and [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/ListIndices?lang=JAVA&tab=DEMO) for multiple languages. ## Python ``` def list_indices(client, workspace_id): """ Gets the details of knowledge bases in a specified workspace. Args: client (bailian20231229Client): The client. workspace_id (str): The workspace ID. Returns: The response from the Alibaba Cloud Model Studio service. """ headers = {} list_indices_request = bailian_20231229_models.ListIndicesRequest() runtime = util_models.RuntimeOptions() return client.list_indices_with_options(workspace_id, list_indices_request, headers, runtime) ``` ## Java ``` /** * Gets the details of knowledge bases in a specified workspace. * * @param client The client. * @param workspaceId The workspace ID. * @return The response from the Alibaba Cloud Model Studio service. */ public ListIndicesResponse listIndices(com.aliyun.bailian20231229.Client client, String workspaceId) throws Exception { Map<String, String> headers = new HashMap<>(); com.aliyun.bailian20231229.models.ListIndicesRequest listIndicesRequest = new com.aliyun.bailian20231229.models.ListIndicesRequest(); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); return client.listIndicesWithOptions(workspaceId, listIndicesRequest, headers, runtime); } ``` ## PHP ``` /** * Gets the details of knowledge bases in a specified workspace. * * @param Bailian $client The client object. * @param string $workspaceId The workspace ID. * @return ListIndicesResponse The response from the Alibaba Cloud Model Studio service. * @throws Exception */ public function listIndices($client, $workspaceId) { $headers = []; $listIndicesRequest = new ListIndicesRequest([]); $runtime = new RuntimeOptions([]); return $client->listIndicesWithOptions($workspaceId, $listIndicesRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Gets the details of knowledge bases in a specified workspace. * @param {bailian20231229.Client} client The client. * @param {string} workspaceId The workspace ID. * @returns {Promise<bailian20231229.ListIndicesResponse>} The response from the Alibaba Cloud Model Studio service. */ async function listIndices(client, workspaceId) { const headers = {}; const listIndicesRequest = new bailian20231229.ListIndicesRequest(); const runtime = new Util.RuntimeOptions({}); return await client.listIndicesWithOptions(workspaceId, listIndicesRequest, headers, runtime); } ``` ## C# ``` /// <summary> /// Gets the details of knowledge bases in a specified workspace. /// </summary> /// <param name="client">The client.</param> /// <param name="workspaceId">The workspace ID.</param> /// <returns>The response from the Alibaba Cloud Model Studio service.</returns> public AlibabaCloud.SDK.Bailian20231229.Models.ListIndicesResponse ListIndices(AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId) { var headers = new Dictionary<string, string>() { }; var listIndicesRequest = new Bailian20231229.Models.ListIndicesRequest(); var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.ListIndicesWithOptions(workspaceId, listIndicesRequest, headers, runtime); } ``` ## Go ``` // listIndices gets the details of knowledge bases in a specified workspace. // // Parameters: // - client *bailian20231229.Client: The client. // - workspaceId string: The workspace ID. // // Returns: // - *bailian20231229.ListIndicesResponse: The response from the Alibaba Cloud Model Studio service. // - error: The error information. func listIndices(client *bailian20231229.Client, workspaceId string) (_result *bailian20231229.ListIndicesResponse, _err error) { headers := make(map[string]*string) listIndicesRequest := &bailian20231229.ListIndicesRequest{} runtime := &util.RuntimeOptions{} return client.ListIndicesWithOptions(tea.String(workspaceId), listIndicesRequest, headers, runtime) } ``` **Sample request** ``` { "WorkspaceId": "llm-4u5xpd1xdjqpxxxx" } ``` **Sample response** ``` { "Status": "200", "RequestId": "5ACB2EB3-6C9A-5B0F-8E60-3FBE7EXXXXXX", "Message": "success", "Data": { "TotalCount": "1", "PageSize": "10", "PageNumber": "1", "Indices": [ { "DocumentIds": [ "file_0b21e0a852cd40cd9741c54fefbb61cd_10xxxxxx" ], "Description": "", "OverlapSize": 100, "SinkInstanceId": "gp-2zegk3i6ca4xxxxxx", "SourceType": "DATA_CENTER_FILE", "RerankModelName": "gte-rerank-hybrid", "SinkRegion": "cn-beijing", "Name": "Model Studio Mobile Phone Knowledge Base", "ChunkSize": 500, "EmbeddingModelName": "text-embedding-v2", "RerankMinScore": 0.01, "Id": "mymxbdxxxx", "SinkType": "BUILT_IN", "Separator": " \\|,\\|，\\|。\\|？\\|！\\|\\n\\|\\\\?\\|\\\\!" } ] }, "Code": "Success", "Success": "true" } ``` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ### **Delete a knowledge base** To permanently delete a knowledge base, call the [DeleteIndex](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-deleteindex) operation. Before you delete the knowledge base, you must [disassociate it from all linked Alibaba Cloud Model Studio applications](https://help.aliyun.com/en/model-studio/rag-knowledge-base#a78dc244578vx) in the Model Studio console. Otherwise, the deletion fails. - **client:** [How to obtain the client](#52ff2774f0pq9) - **workspace\\_id:** [How to obtain the workspace ID](https://help.aliyun.com/en/model-studio/use-workspace#c5222ec081sbo) > A RAM user can delete knowledge bases only in [workspaces they have joined](https://help.aliyun.com/en/model-studio/grant-the-business-space-permission-to-ram-users). - **index\\_id:** Pass the `Data.Id` returned when you [initialize the knowledge base](#00ded5ee90ffx). Note: This operation does not delete the files you have [added to a category](#494345d4b1hx2). | **Important** - Before calling this operation, a RAM user must have the required [API permissions](https://help.aliyun.com/en/model-studio/member-management#a2e8c1d6246s2) by attaching the AliyunBailianDataFullAccess policy. - This operation supports [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/DeleteIndex) and [sample code generation](https://api.aliyun.com/api/bailian/2023-12-29/DeleteIndex?lang=JAVA&tab=DEMO) for multiple languages. ## Python ``` def delete_index(client, workspace_id, index_id): """ Permanently deletes the specified knowledge base. Args: client (bailian20231229Client): The client. workspace_id (str): The workspace ID. index_id (str): The knowledge base ID. Returns: The response from the Alibaba Cloud Model Studio service. """ headers = {} delete_index_request = bailian_20231229_models.DeleteIndexRequest( index_id=index_id ) runtime = util_models.RuntimeOptions() return client.delete_index_with_options(workspace_id, delete_index_request, headers, runtime) ``` ## Java ``` /** * Permanently deletes the specified knowledge base. * * @param client The client. * @param workspaceId The workspace ID. * @param indexId The knowledge base ID. * @return The response from the Alibaba Cloud Model Studio service. */ public DeleteIndexResponse deleteIndex(com.aliyun.bailian20231229.Client client, String workspaceId, String indexId) throws Exception { Map<String, String> headers = new HashMap<>(); com.aliyun.bailian20231229.models.DeleteIndexRequest deleteIndexRequest = new com.aliyun.bailian20231229.models.DeleteIndexRequest(); deleteIndexRequest.setIndexId(indexId); com.aliyun.teautil.models.RuntimeOptions runtime = new com.aliyun.teautil.models.RuntimeOptions(); return client.deleteIndexWithOptions(workspaceId, deleteIndexRequest, headers, runtime); } ``` ## PHP ``` /** * Permanently deletes the specified knowledge base. * * @param Bailian $client The client object. * @param string $workspaceId The workspace ID. * @param string $indexId The knowledge base ID. * @return mixed The response from the Alibaba Cloud Model Studio service. * @throws Exception */ public function deleteIndex($client, $workspaceId, $indexId) { $headers = []; $deleteIndexRequest = new DeleteIndexRequest([ "indexId" => $indexId ]); $runtime = new RuntimeOptions([]); return $client->deleteIndexWithOptions($workspaceId, $deleteIndexRequest, $headers, $runtime); } ``` ## Node.js ``` /** * Permanently deletes the specified knowledge base. * @param {bailian20231229.Client} client The client. * @param {string} workspaceId The workspace ID. * @param {string} indexId The knowledge base ID. * @returns {Promise<bailian20231229.DeleteIndexResponse>} The response from the Alibaba Cloud Model Studio service. */ async function deleteIndex(client, workspaceId, indexId) { const headers = {}; const deleteIndexRequest = new bailian20231229.DeleteIndexRequest({ indexId }); const runtime = new Util.RuntimeOptions({}); return await client.deleteIndexWithOptions(workspaceId, deleteIndexRequest, headers, runtime); } ``` ## C# ``` /// <summary> /// Permanently deletes the specified knowledge base. /// </summary> /// <param name="client">The client.</param> /// <param name="workspaceId">The workspace ID.</param> /// <param name="indexId">The knowledge base ID.</param> /// <returns>The response from the Alibaba Cloud Model Studio service.</returns> public AlibabaCloud.SDK.Bailian20231229.Models.DeleteIndexResponse DeleteIndex(AlibabaCloud.SDK.Bailian20231229.Client client, string workspaceId, string indexId) { var headers = new Dictionary<string, string>() { }; var deleteIndexRequest = new Bailian20231229.Models.DeleteIndexRequest { IndexId = indexId }; var runtime = new AlibabaCloud.TeaUtil.Models.RuntimeOptions(); return client.DeleteIndexWithOptions(workspaceId, deleteIndexRequest, headers, runtime); } ``` ## Go ``` // deleteIndex permanently deletes the specified knowledge base. // // Parameters: // - client *bailian20231229.Client: The client. // - workspaceId string: The workspace ID. // - indexId string: The knowledge base ID. // // Returns: // - *bailian20231229.DeleteIndexResponse: The response from the Alibaba Cloud Model Studio service. // - error: The error information. func deleteIndex(client *bailian20231229.Client, workspaceId, indexId string) (_result *bailian20231229.DeleteIndexResponse, _err error) { headers := make(map[string]*string) deleteIndexRequest := &bailian20231229.DeleteIndexRequest{ IndexId: tea.String(indexId), } runtime := &util.RuntimeOptions{} return client.DeleteIndexWithOptions(tea.String(workspaceId), deleteIndexRequest, headers, runtime) } ``` **Sample request** ``` { "IndexId": "mymxbdxxxx", "WorkspaceId": "llm-4u5xpd1xdjqpxxxx" } ``` **Sample response** ``` { "Status": "200", "Message": "success", "RequestId": "118CB681-75AA-583B-8D84-25440CXXXXXX", "Code": "Success", "Success": "true" } ``` |

## API

See the [API Catalog (Knowledge Base)](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-dir-knowledge-base/) for a complete list of knowledge base APIs and their request and response parameters.

## FAQ

1.  **How do I automate knowledge base updates and synchronization?**
    
    ## Document search
    
    Use Object Storage Service (OSS) to manage files and Function Compute (FC) to listen for file change events. This setup automatically synchronizes updates to your knowledge base in real time. See [Automate AI knowledge base updates](https://www.aliyun.com/solution/tech-solution/auto-updated-knowledge-base).
    
    ## Data query and image Q&A
    
    To automatically update a data query/image Q&A knowledge base, build it based on an RDS data table. See [Create a knowledge base](https://help.aliyun.com/en/model-studio/rag-knowledge-base#6028cfefaauhu).
    
    ## Audio and video search
    
    Not supported.
    

2.  **Why is my new knowledge base empty?**
    
    This typically occurs if the [Submit an index job](#bf14fb34a58vy) step fails to run. If you call the [CreateIndex](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-createindex) API but the [SubmitIndexJob](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-submitindexjob) API call fails, the knowledge base will be empty. To resolve this, [Submit an index job](#bf14fb34a58vy) again and [wait for the index job to complete](#402c6d08c3k71).
    

3.  **What should I do if I receive the error "Access your uploaded file failed. Please check if your upload action was successful"?**
    
    This error usually occurs because the [Upload the file to temporary storage](#a275d1cdd2gph) step did not run successfully. Confirm that this step runs successfully before you call the [AddFile](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-addfile) API operation.
    

4.  **What should I do if I receive the error "Access denied: Either you are not authorized to access this workspace, or the workspace does not exist"?**
    
    This error usually occurs for the following reasons:
    
    -   **The requested service endpoint (**[service endpoint](https://help.aliyun.com/en/model-studio/api-bailian-2023-12-29-endpoint)**) is incorrect:** For access over the Internet, users of the China site (public cloud) should use the service endpoint in China (Beijing), whereas users of the international site should use the service endpoint in Singapore. If you are using the [online debugging](https://api.aliyun.com/api/bailian/2023-12-29/CreateIndex) feature, make sure that you select the correct service endpoint, as shown in the following figure.
        
        ![image](https://help-static-aliyun-doc.aliyuncs.com/assets/img/en-US/5842858671/p952092.png)
        
    -   **The** `**WorkspaceId**` **value is incorrect, or you are not a member of the workspace:** Before you call the API, verify that the `WorkspaceId` is correct and that you are a member of the workspace. [How to be added as a member of a specified workspace](https://help.aliyun.com/en/model-studio/grant-the-business-space-permission-to-ram-users)
        

5.  **What should I do if I receive the error "Specified access key is not found or invalid"?**
    
    This error usually occurs because the provided `access_key_id` or `access_key_secret` is incorrect, or the `access_key_id` has been [disabled](https://help.aliyun.com/en/ram/user-guide/disable-an-accesskey-pair-of-a-ram-user). Ensure that the `access_key_id` is correct and not disabled before you call the API.
    

6.  **What should I do if I receive the error "Category is mismatched"?**
    
    This error typically occurs when the `CategoryId` used in the `ApplyFileUploadLease` API call differs from the `CategoryId` passed in the subsequent `AddFile` API call.
    
    Ensure that you use the same `CategoryId` throughout the entire file upload flow, from `ApplyFileUploadLease` to `AddFile`. You can call the `ListCategory` API to retrieve the list of categories in the current workspace and verify that the `CategoryId` you are using is correct.
    

## Billing

Knowledge bases use **pay-as-you-go (postpaid)** billing. Fees for the following billable items are calculated **hourly** and automatically deducted from your Alibaba Cloud account. Ensure your account has a sufficient balance (you can add funds at [Billing and Costs](https://usercenter2.aliyun.com/home)) to prevent service interruptions due to an [overdue payment](https://help.aliyun.com/en/model-studio/billing-for-knowledge-base#ece89cd5852lm).

| **Billable item** | **Description** |
| --- | --- |
| **Specification fee** | The fee for the actual runtime of a `Standard` or `Flagship` edition knowledge base. For pricing details, see [Knowledge Base Pricing](https://help.aliyun.com/en/model-studio/billing-for-knowledge-base). Configuration changes trigger [segmented billing](https://help.aliyun.com/en/model-studio/billing-for-knowledge-base#d90304901atdb). |
| **Embedding and rerank model call fees** | Calling embedding and rerank models during the creation, update, or retrieval of a knowledge base incurs fees. Billing is based on input token usage. For pricing details, see [Model Pricing](https://help.aliyun.com/en/model-studio/model-pricing). |

**Bill details:** [bill details](https://usercenter2.aliyun.com/finance/expense-report/expense-detail)

## Error codes

If a call to an API operation described in this topic fails, see [Error Center](https://api.aliyun.com/document/bailian/2023-12-29/errorCode).