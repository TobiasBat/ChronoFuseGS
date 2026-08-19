#include "DisasterData.h"
#include "JsonObjectConverter.h"

bool FCameraData::ReadIn(FFilePath FilePath, TArray<FCameraData>& CamerasData, FVector PosTranslate, float Scale)
{
	if (!FPlatformFileManager::Get().GetPlatformFile().FileExists((*FilePath.FilePath)))
	{
		UE_LOG(LogTemp, Error, TEXT("Camera File does not exist: %s"), *FilePath.FilePath);
		return false;
	}
	
	FString JsonStr = "";
	if (!FFileHelper::LoadFileToString(JsonStr, *FilePath.FilePath))
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to Load File to String"));
		return false; 
	}
	
	TSharedPtr<FJsonValue> RootValue;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonStr);

	if (!FJsonSerializer::Deserialize(Reader, RootValue) || !RootValue.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to deserialize JSON"));
		return false;
	}
	
	// Root should be an array of objects
	if (RootValue->Type != EJson::Array)
	{
		UE_LOG(LogTemp, Error, TEXT("Root JSON is not an array"));
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>& RootArray = RootValue->AsArray();
	for (const auto Camera : RootArray)
	{
		FCameraData CameraData;
		TSharedPtr<FJsonObject> ElemObj = Camera->AsObject();
		
		ElemObj->TryGetStringField(TEXT("id"), CameraData.Id);
		ElemObj->TryGetStringField(TEXT("img_name"), CameraData.ImgName);
		ElemObj->TryGetNumberField(TEXT("width"), CameraData.Width);
		ElemObj->TryGetNumberField(TEXT("height"), CameraData.Height);
		ElemObj->TryGetNumberField(TEXT("fy"), CameraData.Fy);
		ElemObj->TryGetNumberField(TEXT("fx"), CameraData.Fx);

		// Positions		
		const TArray<TSharedPtr<FJsonValue>>* PosArray = nullptr;
		ElemObj->TryGetArrayField(TEXT("position"), PosArray);
		TArray<double> Position; 
		for (const auto &PosValue : *PosArray)
		{
			Position.Add((double)PosValue->AsNumber());
		}
		CameraData.Position = FVector(
			(Position[0] - PosTranslate.X) * Scale,
			(Position[2] - PosTranslate.Y) * -Scale,
			(Position[1] - PosTranslate.Z) * -Scale
			); 
		
		// Parse Rotation
		FMatrix RotationMat = FMatrix::Identity;
		const TArray<TSharedPtr<FJsonValue>>* RotationArr = nullptr;
		if (!ElemObj->TryGetArrayField(TEXT("rotation"), RotationArr))
		{
			UE_LOG(LogTemp, Warning, TEXT("No 'rotation' field or not an array - skipping"));
		}
		int RotRow = 0;
		for (const auto &RowValue : *RotationArr)
		{
			const TArray<TSharedPtr<FJsonValue>>& RowArray = RowValue->AsArray();
			int RotCol = 0;
			for (const auto value : RowArray)
			{
				float ValueNumber = value->AsNumber();
				RotationMat.M[RotRow][RotCol] = ValueNumber; 
				RotCol++;
			}
			RotRow++; 
		}
		
		RotationMat.RemoveScaling();
		FQuat QuatSrc = RotationMat.ToQuat();
		FQuat Quat = FQuat(QuatSrc.X, -QuatSrc.Z, -QuatSrc.Y, QuatSrc.W);
		Quat.Normalize();
		
		FQuat RotAroundZ = FQuat(0.0, 0.0, sin(PI/4.0), -sin(PI/4.0));
		RotAroundZ.Normalize();
		
		FQuat QuatRight = Quat * RotAroundZ;
		QuatRight.Normalize();
		
		CameraData.Rotator = QuatRight.Rotator();
		CamerasData.Add(CameraData); 
	}
	return true; 
}

bool FActivationData::ReadIn(FActivationData& OutData, FFilePath FilePath)
{
	DisasterSplattingData ActivationData;
	ReadPlyFile::Read(&ActivationData,FilePath);

	const int NumT = ActivationData.Elements["vertex"].PropertiesKeys.Num() / (1 + 3);
	const int NumSplats = ActivationData.Elements["vertex"].Number;

	OutData.number_of_steps = NumT;
	OutData.opacity.SetNumUninitialized(NumSplats * NumT);
	OutData.color.SetNumUninitialized(NumSplats * NumT * 3);

	for (int i = 0; i < NumSplats; i++)
	{
		for (int t = 0; t < NumT; t++)
		{
			OutData.opacity[i * NumT + t] = ActivationData.Elements["Vertex"].Properties[TEXT("opacity_") + FString::FromInt(t)].Values[i];
			OutData.color[i * NumT * 3 + t * 3 + 0] = ActivationData.Elements["Vertex"].Properties[TEXT("color_r_") + FString::FromInt(t)].Values[i];
			OutData.color[i * NumT * 3 + t * 3 + 1] = ActivationData.Elements["Vertex"].Properties[TEXT("color_g_") + FString::FromInt(t)].Values[i];
			OutData.color[i * NumT * 3 + t * 3 + 2] = ActivationData.Elements["Vertex"].Properties[TEXT("color_b_") + FString::FromInt(t)].Values[i];
		}
	}
	
	return true; 
}

bool FActivationData::ReadInJSON(FActivationData& OutData, FFilePath FilePath)
{
	UE_LOG(LogTemp, Log, TEXT("Reading activation file ..."));
	FString JsonStr = ""; 
	
	if (!FFileHelper::LoadFileToString(JsonStr, *FilePath.FilePath))
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to Load File to String"));
		return false; 
	}
	
	TSharedPtr<FJsonObject> JsonObject;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonStr), JsonObject))
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to deserialize JSON object"));
		return false;
	}

	if (!FJsonObjectConverter::JsonObjectToUStruct<FActivationData>(JsonObject.ToSharedRef(), &OutData))
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to Convert to ActivationData"));
		return  false; 
	}
	
	UE_LOG(LogTemp, Log, TEXT("Activation Data Done"));
	return true;
}

bool FBoundingArea::ReadIn(FBoundingArea& OutData, FFilePath FilePath, FVector PosTranslate, float Scale)
{
	
	if (!FPlatformFileManager::Get().GetPlatformFile().FileExists(*FilePath.FilePath))
	{
		return false;
	}

	FString JsonStr = ""; 
	if (!FFileHelper::LoadFileToString(JsonStr, *FilePath.FilePath))
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to Load File to String"));
		return false; 
	}

	TSharedPtr<FJsonObject> JsonObject;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonStr), JsonObject))
	{
		UE_LOG(LogTemp, Error, TEXT("Failed to deserialize JSON object"));
		return false;
	}
	
	// Parse Rotation
	TArray<FVector> Positions;
	Positions.Init(FVector::ZeroVector, 4);
	
	const TArray<TSharedPtr<FJsonValue>>* PositionArr = nullptr;
	if (!JsonObject->TryGetArrayField(TEXT("bounding_area_model"), PositionArr))
	{
		UE_LOG(LogTemp, Warning, TEXT("No 'rotation' field or not an array - skipping"));
	}
	int RotRow = 0;
	for (const auto &RowValue : *PositionArr)
	{
		const TArray<TSharedPtr<FJsonValue>>& RowArray = RowValue->AsArray();
		int RotCol = 0;
		for (const auto value : RowArray)
		{
			float ValueNumber = value->AsNumber();
			Positions[RotRow][RotCol] = ValueNumber; 
			RotCol++;
		}
		RotRow++; 
	}

	OutData.Positions.Init(FVector::ZeroVector, 4);
	for (int i = 0; i < Positions.Num(); i++)
	{
		OutData.Positions[i] = FVector(
			(Positions[i][0] - PosTranslate.X) * -Scale,
			(Positions[i][2] - PosTranslate.Y) * -Scale,
			0.0
		); 
	}
	
	return true; 
}

