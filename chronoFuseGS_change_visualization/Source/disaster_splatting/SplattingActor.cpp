// Fill out your copyright notice in the Description page of Project Settings.

#include "SplattingActor.h"

#include <cmath>

#include "InterchangeTranslatorBase.h"
#include "JsonObjectConverter.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TextureRenderTarget2D.h"
#include "GameFramework/Character.h"
#include "GeometryCollection/GeometryCollectionConvexUtility.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Kismet/GameplayStatics.h"


// Sets default values
ASplattingActor::ASplattingActor()
{
	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;

	RenderMode = 0; 
	MaxNumberSplats = 100000000;
	MaxNumberNiagaraComponents = 1;
	ShDegree = 0;
	Scale = 100.0f;
	PosTranslate = FVector(0, 0, 0);
	ShowCameraIndicators = true;

	ActivationSelection.Init(0.0, 4);
	ActivationSelectionNorm.Init(0.25, 4);
	ActivationSelection[0] = 1.0;

	ColorActMult = 2.0f;
	ColorActShift = 0.0f;

	ChangeColorSaturation = 0.0f;
	ChangeColorBrightness = 0.5f;
	ChangeColorContrast = 1.0f;
	
	ChangeB = 0.1;
	ChangeK = 3.0; 
	ApplyBoundingArea = false;
	BoundingAreaFromFile = false;
	UserBoundingArea.Init(FVector::ZeroVector, 4);
	
	RenderMaxOpacity = true;

	VR = false;

	bFPSTestRunning = false;
	bFPSTestRecording = false;
	FPSTestCameraIndex = 0;
	FPSTestCameraCount = 0;
	FPSTestSlotElapsed = 0.0f;
	FPSTestFromPos = FVector::ZeroVector;
	FPSTestToPos = FVector::ZeroVector;
	FPSTestFromRot = FQuat::Identity;
	FPSTestToRot = FQuat::Identity;
}

// Called when the game starts or when spawned
void ASplattingActor::BeginPlay()
{
	Super::BeginPlay();

	const FFilePath PlyFilePath = FFilePath(ModelFolderPath.Path + "/point_cloud.ply");
	const FFilePath TimeActivationFilePath = FFilePath(ModelFolderPath.Path + "/activation.ply");
	const FFilePath TimeActivationFilePathJSON = FFilePath(ModelFolderPath.Path + "/activation.ply");
	const FFilePath CamFilePath = FFilePath(ModelFolderPath.Path + "/cameras.json");
	const FFilePath BoundingFilePath = FFilePath(ModelFolderPath.Path + "/bounding_area.json");

	UE_LOG(LogTemp, Log, TEXT("Ply file path %s"), *PlyFilePath.FilePath);
	UE_LOG(LogTemp, Log, TEXT(" Activation file path %s"), *TimeActivationFilePath.FilePath);

	if (!FPlatformFileManager::Get().GetPlatformFile().FileExists(*PlyFilePath.FilePath))
	{
		UE_LOG(LogTemp, Error, TEXT("Ply file does not exists"));
		return; 
	}
	
	UsesActivationData = false; 
	if (UseActivationFile && FPlatformFileManager::Get().GetPlatformFile().FileExists(*TimeActivationFilePath.FilePath))
	{
		// UsesActivationData = ReadActivationDataPly(&ActivationData, TimeActivationFilePath);
		UsesActivationData = FActivationData::ReadIn(ActivationData, TimeActivationFilePath);
		UE_LOG(LogTemp, Log, TEXT("Using activation data %i"), UsesActivationData);
	} else if (UseActivationFile && FPlatformFileManager::Get().GetPlatformFile().FileExists(*TimeActivationFilePathJSON.FilePath))
	{
		// UsesActivationData = ReadActivationDataJSON(&ActivationData, TimeActivationFilePath);
		UsesActivationData = FActivationData::ReadInJSON(ActivationData, TimeActivationFilePath);
		UE_LOG(LogTemp, Log, TEXT("Using activation data %i"), UsesActivationData);
	} else
	{
		UE_LOG(LogTemp, Error, TEXT("Activation file does not exists"));
	}

	if (UsesActivationData)
	{
		if (ActivationSelection.Num() != ActivationData.number_of_steps)
		{
			UE_LOG(LogTemp, Log, TEXT("Not right number of Activation Selections; Updating to %i!"), ActivationData.number_of_steps);
			if (ActivationSelection.Num() < ActivationData.number_of_steps)
			{
				ActivationSelection.SetNumZeroed( ActivationData.number_of_steps);
				ActivationSelectionNorm.SetNumZeroed( ActivationData.number_of_steps);
				UE_LOG(LogTemp, Log, TEXT("Updated"))
			} else
			{
				ActivationSelection.SetNum(ActivationData.number_of_steps);
				ActivationSelectionNorm.SetNum(ActivationData.number_of_steps);
			}
		}
	} else
	{
		ActivationSelection.SetNum(1);
		ActivationSelection[0] = 1.0; 
		ActivationSelectionNorm.SetNum(1);
	}

	UpdateNormActivation();
	UE_LOG(LogTemp, Log, TEXT("Reading In Gaussian Ply file"));
	ReadPlyFile::Read(&Gaussians,PlyFilePath);
	FCameraData::ReadIn(CamFilePath, CamerasData, PosTranslate, Scale);
	if (BoundingAreaFromFile) {
		FBoundingArea::ReadIn(BoundingArea, BoundingFilePath, PosTranslate, Scale);
		for (auto p : BoundingArea.Positions)
		{
			UE_LOG(LogTemp, Log, TEXT("Bounding Area Positions %f %f %f"), p[0], p[1], p[2]);
			
		}
		if (BoundingArea.Positions.Num() != 4 || UserBoundingArea.Num() != 4)
		{
			UE_LOG(LogTemp, Error, TEXT("Some Problems with the Bounding Areas"));
		} else {
			for (int i = 0; i < 4; i++)
			{
				UserBoundingArea[i] = BoundingArea.Positions[i]; 
			}
		}
	} else
	{
		BoundingArea.Positions.Init(FVector::Zero(), 4);
		for (int i = 0; i < 4; i++)
		{
			BoundingArea.Positions[i] = UserBoundingArea[i];
		}
	}
	UE_LOG(LogTemp, Log, TEXT("Setting Attributes ..."));
	SetAttributes();
	UE_LOG(LogTemp, Log, TEXT("... Attributes Set"));
	SpawnCameraIndicators();
	SetCameraIndicatorVisibility(ShowCameraIndicators);
	SpawnBoundingBoxIndicator();
	
	if (AlignModelToCenter)
	{
		AlignToCenter();
	}
	
}


void ASplattingActor::SetAttributes()
{
	
	UE_LOG(LogTemp, Error, TEXT("Starting Setting attributes ..."));
	
	auto PosX= Gaussians.Elements["vertex"].Properties["x"].Values;
	auto PosY= Gaussians.Elements["vertex"].Properties["y"].Values;
	auto PosZ= Gaussians.Elements["vertex"].Properties["z"].Values;

	if (AlignModelToCenter)
		PosTranslate = GetCenterOfPos(PosX, PosZ, PosY); 
	
	auto F_Dc_0 = Gaussians.Elements["vertex"].Properties["f_dc_0"].Values;
	auto F_Dc_1 = Gaussians.Elements["vertex"].Properties["f_dc_1"].Values;
	auto F_Dc_2 = Gaussians.Elements["vertex"].Properties["f_dc_2"].Values;

	TArray<float> Zeros;
	Zeros.Init(0.0, 1); 

	
	if (Gaussians.Elements["vertex"].PropertiesKeys.Contains(TEXT("f_rest_44")))
	{
		ShDegree = std::min(3, ShDegree);
	} else
	{
		ShDegree = 0; 
	}

	auto F_Rest_0 = ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_0"].Values : Zeros;
	auto F_Rest_1 = ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_1"].Values : Zeros;
	auto F_Rest_2 = ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_2"].Values : Zeros;
	auto F_Rest_3 = ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_3"].Values : Zeros;
	auto F_Rest_4 = ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_4"].Values : Zeros;
	auto F_Rest_5= ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_5"].Values : Zeros;
	auto F_Rest_6 = ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_6"].Values : Zeros;
	auto F_Rest_7 = ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_7"].Values : Zeros;
	auto F_Rest_8 = ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_7"].Values : Zeros;
	auto F_Rest_9 = ShDegree > 0 ? Gaussians.Elements["vertex"].Properties["f_rest_7"].Values : Zeros;
	auto F_Rest_10 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_10"].Values : Zeros;
	auto F_Rest_11 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_11"].Values : Zeros;
	auto F_Rest_12 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_12"].Values : Zeros;
	auto F_Rest_13 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_13"].Values : Zeros;
	auto F_Rest_14 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_14"].Values : Zeros;
	auto F_Rest_15 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_15"].Values : Zeros;
	auto F_Rest_16 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_16"].Values : Zeros;
	auto F_Rest_17 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_17"].Values : Zeros;
	auto F_Rest_18 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_18"].Values : Zeros;
	auto F_Rest_19 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_19"].Values : Zeros;
	auto F_Rest_20 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_20"].Values : Zeros;
	auto F_Rest_21 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_21"].Values : Zeros;
	auto F_Rest_22 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_22"].Values : Zeros;
	auto F_Rest_23 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_23"].Values : Zeros;
	auto F_Rest_24 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_24"].Values : Zeros;
	auto F_Rest_25 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_25"].Values : Zeros;
	auto F_Rest_26 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_26"].Values : Zeros;
	auto F_Rest_27 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_27"].Values : Zeros;
	auto F_Rest_28 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_28"].Values : Zeros;
	auto F_Rest_29 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_29"].Values : Zeros;
	auto F_Rest_30 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_30"].Values : Zeros;
	auto F_Rest_31 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_31"].Values : Zeros;
	auto F_Rest_32 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_32"].Values : Zeros;
	auto F_Rest_33 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_33"].Values : Zeros;
	auto F_Rest_34 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_34"].Values : Zeros;
	auto F_Rest_35 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_35"].Values : Zeros;
	auto F_Rest_36 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_36"].Values : Zeros;
	auto F_Rest_37 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_37"].Values : Zeros;
	auto F_Rest_38 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_38"].Values : Zeros;
	auto F_Rest_39 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_39"].Values : Zeros;
	auto F_Rest_40 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_40"].Values : Zeros;
	auto F_Rest_41 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_41"].Values : Zeros;
	auto F_Rest_42 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_42"].Values : Zeros;
	auto F_Rest_43 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_43"].Values : Zeros;
	auto F_Rest_44 =ShDegree > 0 ?  Gaussians.Elements["vertex"].Properties["f_rest_44"].Values : Zeros;
		
	auto OpacitiesRaw = Gaussians.Elements["vertex"].Properties["opacity"].Values;

	auto Rot_0 = Gaussians.Elements["vertex"].Properties["rot_0"].Values;
	auto Rot_1 = Gaussians.Elements["vertex"].Properties["rot_1"].Values;
	auto Rot_2 = Gaussians.Elements["vertex"].Properties["rot_2"].Values;
	auto Rot_3 = Gaussians.Elements["vertex"].Properties["rot_3"].Values;

	auto Scale_0 = Gaussians.Elements["vertex"].Properties["scale_0"].Values;
	auto Scale_1 = Gaussians.Elements["vertex"].Properties["scale_1"].Values;
	auto Scale_2 = Gaussians.Elements["vertex"].Properties["scale_2"].Values;

	UE_LOG(LogTemp, Error, TEXT("Got Individual Values"));
	
	TArray<FVector> Pos;
	for (auto i = 0; i < PosX.Num(); i++)
	{
		Pos.Add(FVector(
		(PosX[i] - PosTranslate.X) * Scale,
		(PosZ[i] - PosTranslate.Y) * -Scale,
		(PosY[i] - PosTranslate.Z) * -Scale
		));
	}
	
	TArray<float> Harmonics;
	for (auto i = 0; i < F_Dc_0.Num(); i++)
	{
		Harmonics.Add(F_Dc_0[i]);
		Harmonics.Add(F_Dc_1[i]);
		Harmonics.Add(F_Dc_2[i]);
		if (ShDegree > 0) {
			Harmonics.Add(F_Rest_0[i]);
			Harmonics.Add(F_Rest_1[i]); 
			Harmonics.Add(F_Rest_2[i]);
			Harmonics.Add(F_Rest_3[i]);
			Harmonics.Add(F_Rest_4[i]);
			Harmonics.Add(F_Rest_5[i]);
			Harmonics.Add(F_Rest_6[i]);
			Harmonics.Add(F_Rest_7[i]);
			Harmonics.Add(F_Rest_8[i]); 
			Harmonics.Add(F_Rest_9[i]); 
			Harmonics.Add(F_Rest_10[i]);
			Harmonics.Add(F_Rest_11[i]);
			Harmonics.Add(F_Rest_12[i]);
			Harmonics.Add(F_Rest_13[i]);
			Harmonics.Add(F_Rest_14[i]);
			Harmonics.Add(F_Rest_15[i]);
			Harmonics.Add(F_Rest_16[i]);
			Harmonics.Add(F_Rest_17[i]);
			Harmonics.Add(F_Rest_18[i]);
			Harmonics.Add(F_Rest_19[i]);
			Harmonics.Add(F_Rest_20[i]);
			Harmonics.Add(F_Rest_21[i]);
			Harmonics.Add(F_Rest_22[i]);
			Harmonics.Add(F_Rest_23[i]);
			Harmonics.Add(F_Rest_24[i]);
			Harmonics.Add(F_Rest_25[i]);
			Harmonics.Add(F_Rest_26[i]);
			Harmonics.Add(F_Rest_27[i]);
			Harmonics.Add(F_Rest_28[i]);
			Harmonics.Add(F_Rest_29[i]);
			Harmonics.Add(F_Rest_30[i]);
			Harmonics.Add(F_Rest_31[i]);
			Harmonics.Add(F_Rest_32[i]);
			Harmonics.Add(F_Rest_33[i]);
			Harmonics.Add(F_Rest_34[i]); 
			Harmonics.Add(F_Rest_35[i]);
			Harmonics.Add(F_Rest_36[i]);
			Harmonics.Add(F_Rest_37[i]);
			Harmonics.Add(F_Rest_38[i]);
			Harmonics.Add(F_Rest_39[i]); 
			Harmonics.Add(F_Rest_40[i]);
			Harmonics.Add(F_Rest_41[i]);
			Harmonics.Add(F_Rest_42[i]);
			Harmonics.Add(F_Rest_43[i]);
			Harmonics.Add(F_Rest_44[i]);
		}
	}

	TArray<float> Opacities;
	Opacities.SetNumUninitialized(OpacitiesRaw.Num()); 
	for (auto i = 0; i < OpacitiesRaw.Num(); i++)
	{
		Opacities[i] = 1.0 / (1.0 + exp(-OpacitiesRaw[i]));
	}

	TArray<float> Rotations;
	for (auto i = 0; i < Rot_0.Num(); i++)
	{
		double length = std::sqrt(Rot_0[i] * Rot_0[i] + Rot_1[i] * Rot_1[i] + Rot_2[i] * Rot_2[i] + Rot_3[i] * Rot_3[i]);

		// TODO add is slow
		Rotations.Add(Rot_1[i] / length);
		Rotations.Add(-Rot_3[i] / length);
		Rotations.Add(-Rot_2[i] / length);
		Rotations.Add(Rot_0[i] / length);
	}

	TArray<float> Scales;
	for (auto i = 0; i < Scale_0.Num(); i++)
	{
		Scales.Add(exp(Scale_0[i]) * Scale);
		Scales.Add(exp(Scale_2[i]) * -Scale);
		Scales.Add(exp(Scale_1[i]) * -Scale);
	}

	TArray<float> OpacityActivation;
	OpacityActivation.SetNumUninitialized(ActivationData.opacity.Num()); 
	TArray<float> ColorActivation;
	ColorActivation.SetNumUninitialized(ActivationData.color.Num());
	
	int32 OpacityActivationNumberOfSteps = 1;
	UE_LOG(LogTemp, Error, TEXT("Number of Color Activation values: %i"), ActivationData.color.Num());
	
	if (UsesActivationData) {
		OpacityActivationNumberOfSteps  = ActivationData.number_of_steps;
		for (auto i = 0; i < ActivationData.opacity.Num(); i++)
		{
			OpacityActivation[i] = 1.0 / (1.0 + exp(-ActivationData.opacity[i])); 
		}
		for (int i = 0; i < ActivationData.color.Num(); i++)
		{
			ColorActivation[i] = ColorActMult / (1.0 + exp(-ActivationData.color[i])) + ColorActShift;
		}
	} else
	{
		OpacityActivation.Init(1.0, OpacitiesRaw.Num());
		ColorActivation.Init(1.0, OpacitiesRaw.Num() * 3);
	}

	// Transform the Colors to Vec3 
	TArray<FVector> ChangeGradientVectors;
	ChangeGradientVectors.Reserve(ChangeGradient->ChangeGradient.Num());
	for (const FLinearColor& Color : ChangeGradient->ChangeGradient)
	{
		ChangeGradientVectors.Add(FVector(Color.R, Color.G, Color.B));
	}
	
	UE_LOG(LogTemp, Error, TEXT("Total number of Splats: %i"), Pos.Num());
	int NumColorsPerSplat = ShDegree < 1 ? 1 : 48;
	auto NumOfSystem = std::ceil(PosX.Num() / MaxNumberSplats); 
	for (auto i = 0; i <= std::ceil(PosX.Num() / MaxNumberSplats) && i < MaxNumberNiagaraComponents; i++)
	{
		
		UNiagaraComponent* NiagaraComponent = UNiagaraFunctionLibrary::SpawnSystemAttached(
			NiagaraSystem,
			RootComponent,
			NAME_None,
			FVector(0.f),
			FRotator(0.f),
			EAttachLocation::Type::KeepRelativeOffset,
			false,
			true,
			ENCPoolMethod::None,
			false
		);

		UNiagaraComponent* NiagaraPositionComp = nullptr;
		if (PositionNiagaraSystem != nullptr)
		{
			NiagaraPositionComp = UNiagaraFunctionLibrary::SpawnSystemAttached(
			PositionNiagaraSystem,
			RootComponent,
			NAME_None,
			FVector(0.f),
			FRotator(0.f),
			EAttachLocation::Type::KeepRelativeOffset,
			false,
			true,
			ENCPoolMethod::None,
			false
		);
		}

		if (NumOfSystem == 0)
		{
			UE_LOG(LogTemp, Error, TEXT("Setting complete data"));
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(NiagaraComponent, FName("PosIn"), Pos);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("HarmonicsIn"), Harmonics);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("OpacityIn"), Opacities);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("OrientationIn"), Rotations);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("ScaleIn"), Scales);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("OpacityActivationIn"), OpacityActivation);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("ColorActivationIn"), ColorActivation);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("TimeSelectionIn"), ActivationSelection);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("TimeSelectionNormIn"), ActivationSelectionNorm);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(NiagaraComponent, FName("BoundingAreaIn"), BoundingArea.Positions);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(NiagaraComponent, FName("GradientRGBColorsIn"), ChangeGradientVectors);
			NiagaraComponent->SetVariableInt(FName("RenderMode"), RenderMode);
			NiagaraComponent->SetVariableBool(FName("applyBoundingArea"), ApplyBoundingArea);
			NiagaraComponent->SetVariableFloat(FName("ChangeB"), ChangeB);
			NiagaraComponent->SetVariableFloat(FName("ChangeK"), ChangeK);
			NiagaraComponent->SetVariableFloat(FName("ChangeColorContrast"), ChangeColorContrast);
			NiagaraComponent->SetVariableFloat(FName("ChangeColorSaturation"), ChangeColorSaturation);
			NiagaraComponent->SetVariableFloat(FName("ChangeColorBrightness"), ChangeColorBrightness);
			NiagaraComponent->SetVariableBool(FName("VR"), VR);
			NiagaraComponent->SetVariableBool(FName("MaxOpacity"), RenderMaxOpacity);


			if (NiagaraPositionComp != nullptr)
			{
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(NiagaraPositionComp, FName("PosIn"), Pos);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraPositionComp, FName("HarmonicsIn"), Harmonics);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraPositionComp, FName("OpacityIn"), Opacities);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraPositionComp, FName("OrientationIn"), Rotations);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraPositionComp, FName("ScaleIn"), Scales);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraPositionComp, FName("OpacityActivationIn"), OpacityActivation);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraPositionComp, FName("ColorActivationIn"), ColorActivation);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraPositionComp, FName("TimeSelectionIn"), ActivationSelection);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraPositionComp, FName("TimeSelectionNormIn"), ActivationSelectionNorm);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(NiagaraPositionComp, FName("BoundingAreaIn"), BoundingArea.Positions);
				UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(NiagaraPositionComp, FName("GradientRGBColorsIn"), ChangeGradientVectors);
				NiagaraPositionComp->SetVariableInt(FName("RenderMode"), RenderMode);
				NiagaraPositionComp->SetVariableBool(FName("applyBoundingArea"), ApplyBoundingArea);
				NiagaraPositionComp->SetVariableFloat(FName("ChangeB"), ChangeB);
				NiagaraPositionComp->SetVariableFloat(FName("ChangeK"), ChangeK);
				NiagaraPositionComp->SetVariableFloat(FName("ChangeColorContrast"), ChangeColorContrast);
				NiagaraPositionComp->SetVariableFloat(FName("ChangeColorSaturation"), ChangeColorSaturation);
				NiagaraPositionComp->SetVariableFloat(FName("ChangeColorBrightness"), ChangeColorBrightness);
				NiagaraPositionComp->SetVariableBool(FName("VR"), VR);
				NiagaraPositionComp->SetVariableBool(FName("MaxOpacity"), RenderMaxOpacity);
			}
		}
		else
		{
			UE_LOG(LogTemp, Error, TEXT("Split of system: %i"), i);
			int32 Start = MaxNumberSplats * i;
			int32 End = Start + MaxNumberSplats;
		
			auto PosSplit = SplitArray(Pos, Start, End);
			auto HarmonicsSplit = SplitArray(Harmonics, Start * NumColorsPerSplat, End * NumColorsPerSplat); 
			auto OpacitySplit = SplitArray(Opacities, Start, End);
			auto RotationSplit = SplitArray(Rotations, Start * 4, End * 4);
			auto ScaleSplit = SplitArray(Scales, Start * 3, End * 3);
			auto ActivationSplit = SplitArray(
				OpacityActivation,
				Start * OpacityActivationNumberOfSteps,
				End * OpacityActivationNumberOfSteps
			);
			auto ActivationColorSplit = SplitArray(
				ColorActivation,
				Start * OpacityActivationNumberOfSteps * 3,
				End * OpacityActivationNumberOfSteps * 3
			);

			auto BoundingAreaSplit = SplitArray(BoundingArea.Positions, Start, End); 
		
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(NiagaraComponent, FName("PosIn"), PosSplit);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("HarmonicsIn"), HarmonicsSplit);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("OpacityIn"), OpacitySplit);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("OrientationIn"), RotationSplit);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("ScaleIn"), ScaleSplit);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("OpacityActivationIn"), ActivationSplit);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("ColorActivationIn"), ActivationColorSplit);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("TimeSelectionIn"), ActivationSelection);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(NiagaraComponent, FName("TimeSelectionNormIn"), ActivationSelectionNorm);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(NiagaraComponent, FName("BoundingAreaIn"), BoundingAreaSplit);
			UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(NiagaraComponent, FName("GradientRGBColorsIn"), ChangeGradientVectors);
			NiagaraComponent->SetVariableInt(FName("RenderMode"), RenderMode);
			NiagaraComponent->SetVariableBool(FName("applyBoundingArea"), ApplyBoundingArea);
			NiagaraComponent->SetVariableFloat(FName("ChangeB"), ChangeB);
			NiagaraComponent->SetVariableFloat(FName("ChangeK"), ChangeK);
			NiagaraComponent->SetVariableFloat(FName("ChangeColorContrast"), ChangeColorContrast);
			NiagaraComponent->SetVariableFloat(FName("ChangeColorSaturation"), ChangeColorSaturation);
			NiagaraComponent->SetVariableFloat(FName("ChangeColorBrightness"), ChangeColorBrightness);

			UE_LOG(LogTemp, Error, TEXT("System Splats: %i"), PosSplit.Num());
		}
		NiagaraComponents.Add(NiagaraComponent);
		if (NiagaraPositionComp != nullptr)
		{
			NiagaraPositionComp->bVisibleInSceneCaptureOnly = true;
			NiagaraPositionComponents.Add(NiagaraPositionComp);
		}
	}
	UE_LOG(LogTemp, Log, TEXT("Done Setting Attributes")); 
}

void ASplattingActor::UpdateActivationSelectionNiagara()
{
	for (auto Component : NiagaraComponents)
	{
		UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(Component, FName("TimeSelectionIn"), ActivationSelection);
		UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(Component, FName("TimeSelectionNormIn"), ActivationSelectionNorm);
	}
	for (auto Component : NiagaraPositionComponents)
	{
		UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(Component, FName("TimeSelectionIn"), ActivationSelection);
		UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayFloat(Component, FName("TimeSelectionNormIn"), ActivationSelectionNorm);
	}
}


void ASplattingActor::AlignToCenter()
{
	FVector Center = FVector(0.f, 0.f, 0.f);
	for (auto NComponent : NiagaraComponents)
	{
		auto Pos = UNiagaraDataInterfaceArrayFunctionLibrary::GetNiagaraArrayVector(NComponent, FName("PosIn"));
		auto CompCenter = FVector(0.f);
		for (auto P : Pos)
		{
			CompCenter += (P / Pos.Num()); 
		}
		Center += CompCenter;
	}

	Center = Center / NiagaraComponents.Num();
	
	this->SetActorLocation(FVector(Center.X, Center.Y, Center.Z));
	UE_LOG(LogTemp, Log, TEXT("Systems avg center: %s"), *Center.ToString());
	UE_LOG(LogTemp, Log, TEXT("New Actor Center: %s"), *this->GetActorLocation().ToString());
}

void ASplattingActor::SpawnCameraIndicators()
{
	if (CameraBaseActor)
	{
		UWorld* World = GetWorld();
		if (World)
		{
			int i = 0; 
			for (auto& Camera : CamerasData)
			{
				// Define the location (offsetting each copy so they don't overlap)
				FVector SpawnLocation = Camera.Position + GetActorLocation();
				FRotator SpawnRotation = Camera.Rotator + GetActorRotation();

				FActorSpawnParameters SpawnParams;
				SpawnParams.Owner = this;
				SpawnParams.Instigator = GetInstigator();

				// The actual spawn call
				AActor* NewSpawn = World->SpawnActor<AActor>(CameraBaseActor, SpawnLocation, SpawnRotation, SpawnParams);
				Camera.Actor = NewSpawn;
				i++; 
			}
		}
	}
}

void ASplattingActor::SpawnBoundingBoxIndicator()
{
	if (BoundingBoxIndicatorActor)
	{
		UWorld* World = GetWorld();
		if (World)
		{
			int i = 0;
			for (auto& Pos : BoundingArea.Positions)
			{
				// Define the location (offsetting each copy so they don't overlap)
				FVector SpawnLocation = Pos + FVector(0,0,30) + GetActorLocation();
				FRotator SpawnRotation = GetActorRotation();

				FActorSpawnParameters SpawnParams;
				SpawnParams.Owner = this;
				SpawnParams.Instigator = GetInstigator();

				// The actual spawn call
				AActor* NewSpawn = World->SpawnActor<AActor>(BoundingBoxIndicatorActor, SpawnLocation, SpawnRotation, SpawnParams);
				BoundingArea.Actors.Add(NewSpawn);
				i++;

				UE_LOG(LogTemp, Log, TEXT("Bounding box indicator pos %f %f %f"), SpawnLocation.X, SpawnLocation.Y, SpawnLocation.Z)
			}
		}
	}
}

FVector ASplattingActor::GetCenterOfPos(TArray<float> Xs, TArray<float> Ys, TArray<float> Zs)
{
	auto Center = FVector(0.f);
	for (auto X : Xs)
	{
		Center.X += X / Xs.Num();
	}
	for (auto Y : Ys)
	{
		Center.Y += Y / Ys.Num();
	}
	for (auto Z : Zs)
	{
		Center.Z += Z / Zs.Num();
	}
	return Center;
}

TArray<FVector> ASplattingActor::SplitArray(TArray<FVector> In, const int32 FirstIndex, const int32 LastIndex)
{
	TArray<FVector> Out;
	for (auto i = FirstIndex; i < LastIndex && i < In.Num(); i++)
	{
		Out.Add(In[i]);
	}
	return Out;
}

TArray<FVector4> ASplattingActor::SplitArray(TArray<FVector4> In, const int32 FirstIndex, const int32 LastIndex)
{
	TArray<FVector4> Out;
	for (auto i = FirstIndex; i < LastIndex && i < In.Num(); i++)
	{
		Out.Add(In[i]);
	}
	return Out;
}

TArray<float> ASplattingActor::SplitArray(TArray<float> In, const int32 FirstIndex, const int32 LastIndex)
{
	TArray<float> Out;
	for (auto i = FirstIndex; i < LastIndex && i < In.Num(); i++)
	{
		Out.Add(In[i]);
	}
	return Out;
}

void ASplattingActor::PrintHeader()
{
	TArray<FString> ElementKeys;
	Gaussians.Elements.GetKeys(ElementKeys);
	for (auto key : ElementKeys) 
	{
		UE_LOG(LogTemp, Log, TEXT("-Element: %s : %i"), *key, Gaussians.Elements[key].Number); 
		for (auto PropertyName : Gaussians.Elements[key].Properties)
		{
			UE_LOG(LogTemp, Log, TEXT("--Property: %s"), *PropertyName.Value.Name);
		}
	}
}

void ASplattingActor::UpdateNormActivation()
{
	float L1 = 0.0;
	for (auto Selection : ActivationSelection)
	{
		L1 += Selection;
	}

	if (ActivationSelectionNorm.Num() != ActivationSelection.Num())
	{
		UE_LOG(LogTemp, Error, TEXT("Activation selections sizes do not match")); 
		return; 
	}
	for (int i = 0; i < ActivationSelection.Num(); i++)
	{
		ActivationSelectionNorm[i] = ActivationSelection[i] / L1;
	}
}

AActor* ASplattingActor::GetCameraActor(int index)
{
	if (index > 0 && index < CamerasData.Num())
	{
		auto Actor = CamerasData[index].Actor;
		auto Rotator = Actor->GetActorRotation();
		UE_LOG(LogTemp, Log, TEXT("rotation %f %f %f"), Rotator.Euler().X, Rotator.Euler().Y, Rotator.Euler().Z);
		return Actor;
	}
	return CamerasData[0].Actor;
}

int ASplattingActor::GetNextCameraIndex(int index, int shift)
{
	int NewIndex = (index + shift);
	if (NewIndex < 0)
	{
		return CamerasData.Num() + NewIndex;
	}
	return NewIndex % CamerasData.Num();
}

void ASplattingActor::SetCameraIndicatorVisibility(bool Visible)
{
	for (auto Camera: CamerasData)
	{
		if (Camera.Actor)
		{
			Camera.Actor->SetActorHiddenInGame(!Visible);
		}
	}	
}

float ASplattingActor::GetFieldOfView(int CameraIndex)
{
	if (CameraIndex < 0 || CameraIndex >= CamerasData.Num() )
	{
		return 0.0f;
	}

	const auto Cam = CamerasData[CameraIndex]; 
	const float FovX = FMath::Atan(Cam.Width / Cam.Fx);
	const float FovXDeg = FMath::RadiansToDegrees(FovX);
	return FovXDeg;
}

void ASplattingActor::SetRenderMode(int RenderIndex)
{
	for (const auto component : NiagaraComponents)
	{
		component->SetVariableInt(FName("RenderMode"), RenderIndex);
	}
}

void ASplattingActor::ShowNextTimeSelection(int Shift)
{
	int FirstViewTime = 0;
	for (int i = 0; i < ActivationSelection.Num(); i++)
	{
		if (ActivationSelection[i] > 0.0)
		{
			FirstViewTime = i;
			break; 
		}
	}

	ActivationSelection.Init(0.0, ActivationSelection.Num());

	int NextTimeView = FirstViewTime + Shift; 	
	if (NextTimeView >= ActivationSelection.Num())
	{
		NextTimeView = 0;
	}
	if (NextTimeView < 0)
	{
		NextTimeView = ActivationSelection.Num() - 1;
	}
	ActivationSelection[NextTimeView] = 1.0;
	UpdateNormActivation(); 
	UpdateActivationSelectionNiagara();
}

void ASplattingActor::ShowAllTimes()
{
	ActivationSelection.Init(1.0, ActivationSelection.Num());
	UpdateNormActivation(); 
	UpdateActivationSelectionNiagara();
}

void ASplattingActor::SetTimeSelection(TArray<float> Selection)
{
	if (Selection.Num() != ActivationSelection.Num())
	{
		UE_LOG(LogTemp, Log, TEXT("Selection has wrong size"));
		return;
	}
	
	ActivationSelection.Init(0.0, ActivationSelection.Num());
	for (int i = 0; i < ActivationSelection.Num(); i++)
	{
		ActivationSelection[i] = Selection[i];
	}
	UpdateNormActivation(); 
	UpdateActivationSelectionNiagara();
}

#if WITH_EDITOR
void ASplattingActor::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);

	const FName PropertyName =
		PropertyChangedEvent.Property
		? PropertyChangedEvent.Property->GetFName()
		: NAME_None;
	UE_LOG(LogTemp, Log, TEXT("Prop Name %s"), *PropertyName.ToString())
	if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, ActivationSelection))
	{
		UE_LOG(LogTemp, Log, TEXT("Activation Selection"));
		UpdateNormActivation(); 
		UpdateActivationSelectionNiagara();
	}
	else if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, ShowCameraIndicators))
	{
		UE_LOG(LogTemp, Log, TEXT("Show Camera Indicators %i"), ShowCameraIndicators);
		SetCameraIndicatorVisibility(ShowCameraIndicators);
	}
	else if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, RenderMode))
	{
		SetRenderMode(RenderMode);
	}
	else if (
		PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, ChangeGradient) 
	)
	{
		UpdateChangeVisParameters();
	} else if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, ChangeK))
	{
		UpdateChangeVisParameters();
	} else if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, ChangeB))
	{
		UpdateChangeVisParameters();
	} else if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, ChangeColorContrast))
	{
		UpdateChangeVisParameters();
	} else if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, ChangeColorBrightness))
	{
		UpdateChangeVisParameters();
	} else if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, ChangeColorSaturation))
	{
		UpdateChangeVisParameters();
	}
	else if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, RenderMaxOpacity))
	{
		UpdateChangeVisParameters();
	}
	else if (PropertyName == GET_MEMBER_NAME_CHECKED(ASplattingActor, UserBoundingArea))
	{
		UpdateBoundingArea();
	}
}
#endif


// Called every frame
void ASplattingActor::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	if (bFPSTestRunning)
	{
		if (bFPSTestRecording)
		{
			FPSTestFrameTimes.Add(DeltaTime);
		}

		if (bFPSTestInterpolate)
		{
			FPSTestSlotElapsed += DeltaTime;
			float Alpha = FMath::Clamp(FPSTestSlotElapsed / FPSTestInterval, 0.0f, 1.0f);
			FVector LerpedPos = FMath::Lerp(FPSTestFromPos, FPSTestToPos, Alpha);
			FQuat LerpedRot = FQuat::Slerp(FPSTestFromRot, FPSTestToRot, Alpha);
			OnFPSTestUpdateTransform(LerpedPos, LerpedRot.Rotator());
		}
	}
}

void ASplattingActor::UpdateChangeVisParameters()
{
	// Transform the Colors to Vec3 
	TArray<FVector> ChangeGradientVectors;
	ChangeGradientVectors.Reserve(ChangeGradient->ChangeGradient.Num());
	for (const FLinearColor& Color : ChangeGradient->ChangeGradient)
	{
		ChangeGradientVectors.Add(FVector(Color.R, Color.G, Color.B));
	}

	for (const auto Component : NiagaraComponents)
	{
		UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(Component, FName("GradientRGBColorsIn"), ChangeGradientVectors);
		Component->SetVariableFloat(FName("ChangeK"), ChangeK);
		Component->SetVariableFloat(FName("ChangeB"), ChangeB);
		Component->SetVariableFloat(FName("ChangeColorContrast"), ChangeColorContrast);
		Component->SetVariableFloat(FName("ChangeColorBrightness"), ChangeColorBrightness);
		Component->SetVariableFloat(FName("ChangeColorSaturation"), ChangeColorSaturation);
		Component->SetVariableBool(FName("MaxOpacity"), RenderMaxOpacity);
	}
}

void ASplattingActor::UpdateBoundingArea()
{
	UE_LOG(LogTemp, Error, TEXT("Updating Bounding Area"));
	BoundingArea.Positions.Init(FVector::Zero(), 4);
	for (int i = 0; i < 4; i++)
	{
		BoundingArea.Positions[i] = UserBoundingArea[i];
	}
	for (const auto Component : NiagaraComponents) {
		UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(Component, FName("BoundingAreaIn"), BoundingArea.Positions);
	}
}

void ASplattingActor::SetActivationSelection(TArray<float> Selection)
{
	for (int Index = 0; Index < Selection.Num() && Index < ActivationSelection.Num(); Index++)
	{
		ActivationSelection[Index] = Selection[Index];
	}
	UpdateActivationSelectionNiagara();
	UpdateNormActivation();
}

int ASplattingActor::NumberOfTimes()
{
	return ActivationSelection.Num();
}


FText ASplattingActor::GetTimeSelectionRepresentation()
{
		if (ActivationSelection.Num() == 0)
		{
			return FText::FromString(TEXT("Empty"));
		}

		TArray<FString> Parts;
		for (int32 i = 0; i < ActivationSelection.Num(); ++i)
		{
			float Value = ActivationSelection[i];

			if (Value == 0)
			{
				Parts.Add(FString::Printf(TEXT("00")));
			} else if (Value >= 1)
			{
				Parts.Add(FString::Printf(TEXT("10")));
			} else
			{
				int SecDig = FMath::FloorToInt(Value * 10.0f);
				Parts.Add(FString::Printf(TEXT("0%i"), SecDig));
			}
		}
		FString Combined = FString::Join(Parts, TEXT("_"));
		return FText::FromString(Combined);
	}

FText ASplattingActor::GetCameraNameFromIndex(int index)
{	
	if (index < CamerasData.Num() && index >= 0) {
		return FText::FromString(CamerasData[index].ImgName); 
	}
	return FText::FromString("");
}

void ASplattingActor::SetParticleFacingPosition(FVector Position)
{
	for (auto Component : NiagaraPositionComponents)
	{
		Component->SetVectorParameter(FName("ParticleFacingPosition"), Position);
	}
}

void ASplattingActor::StartFPSTest(int32 MaxCameras)
{
	if (bFPSTestRunning || CamerasData.Num() == 0) return;

	bFPSTestRunning = true;
	bFPSTestRecording = false;
	FPSTestCameraIndex = 0;
	FPSTestFrameTimes.Empty();
	FPSTestCameraCount = (MaxCameras > 0) ? FMath::Min(MaxCameras, CamerasData.Num()) : CamerasData.Num();

	FPSTest_MoveToCamera();

	// Settle for 10% of the interval, then record every frame until the slot ends
	GetWorldTimerManager().SetTimer(FPSTestSettleTimer, this, &ASplattingActor::FPSTest_StartRecording, FPSTestInterval * 0.1f, false);
	GetWorldTimerManager().SetTimer(FPSTestAdvanceTimer, this, &ASplattingActor::FPSTest_Advance, FPSTestInterval, false);
}

void ASplattingActor::FPSTest_MoveToCamera()
{
	if (FPSTestCameraIndex >= FPSTestCameraCount) return;

	if (bFPSTestInterpolate)
	{
		// From = where we currently are (previous camera, or pawn start pos for index 0)
		if (FPSTestCameraIndex == 0)
		{
			APawn* Pawn = UGameplayStatics::GetPlayerPawn(GetWorld(), 0);
			FPSTestFromPos = Pawn ? Pawn->GetActorLocation() : FVector::ZeroVector;
			FPSTestFromRot = Pawn ? Pawn->GetActorQuat() : FQuat::Identity;
		}
		else
		{
			FPSTestFromPos = FPSTestToPos;
			FPSTestFromRot = FPSTestToRot;
		}

		const FCameraData& Cam = CamerasData[FPSTestCameraIndex];
		FPSTestToPos = Cam.Position + GetActorLocation();
		FPSTestToRot = Cam.Rotator.Quaternion();
		FPSTestSlotElapsed = 0.0f;
	}
	else
	{
		OnFPSTestSwitchCamera(FPSTestCameraIndex);
	}
}

void ASplattingActor::FPSTest_StartRecording()
{
	bFPSTestRecording = true;
}

void ASplattingActor::FPSTest_Advance()
{
	bFPSTestRecording = false;
	FPSTestCameraIndex++;

	if (FPSTestCameraIndex >= FPSTestCameraCount)
	{
		FPSTest_Finish();
		return;
	}

	FPSTest_MoveToCamera();
	GetWorldTimerManager().SetTimer(FPSTestSettleTimer, this, &ASplattingActor::FPSTest_StartRecording, FPSTestInterval * 0.1f, false);
	GetWorldTimerManager().SetTimer(FPSTestAdvanceTimer, this, &ASplattingActor::FPSTest_Advance, FPSTestInterval, false);
}

void ASplattingActor::FPSTest_Finish()
{
	bFPSTestRunning = false;

	if (FPSTestFrameTimes.Num() == 0)
	{
		OnFPSTestComplete(0.0f, 0.0f, 0.0f);
		return;
	}

	// Average FPS
	float Total = 0.0f;
	for (float DT : FPSTestFrameTimes) Total += DT;
	float AvgFrameTime = Total / FPSTestFrameTimes.Num();
	float AvgFPS = AvgFrameTime > 0.0f ? 1.0f / AvgFrameTime : 0.0f;

	// Min FPS (worst single frame = largest frame time)
	float MaxDT = 0.0f;
	for (float DT : FPSTestFrameTimes) MaxDT = FMath::Max(MaxDT, DT);
	float MinFPS = MaxDT > 0.0f ? 1.0f / MaxDT : 0.0f;

	// 1% low: average FPS of the worst 1% of frames (highest frame times)
	TArray<float> Sorted = FPSTestFrameTimes;
	Sorted.Sort(); // ascending — largest frame times at the end
	int32 OnePercentCount = FMath::Max(1, FMath::FloorToInt(Sorted.Num() * 0.01f));
	float SlowTotal = 0.0f;
	for (int32 i = Sorted.Num() - OnePercentCount; i < Sorted.Num(); i++)
	{
		SlowTotal += Sorted[i];
	}
	float OnePercentLow = SlowTotal > 0.0f ? OnePercentCount / SlowTotal : 0.0f;

	OnFPSTestComplete(AvgFPS, OnePercentLow, MinFPS);
}

void ASplattingActor::SetDepthCameraMats(FVector2d ViewSize, FVector4 ViewT, FMatrix ViewW2V, FMatrix ViewV2C, FMatrix ViewC2W)
{
	// UE_LOG(LogTemp, Error, TEXT("ViewSize Vec: %s"), *ViewSize.ToString());
	// UE_LOG(LogTemp, Error, TEXT("ViewT Vec: %s"), *ViewT.ToString());
	// UE_LOG(LogTemp, Error, TEXT("ViewW2V Matrix: %s"), *ViewW2V.ToString());
	// UE_LOG(LogTemp, Error, TEXT("ViewV2C Matrix: %s"), *ViewV2C.ToString());
	// UE_LOG(LogTemp, Error, TEXT("ViewC2W Matrix: %s"), *ViewC2W.ToString());
	// UE_LOG(LogTemp, Log, TEXT("-")); 
	for (const auto Comp : NiagaraPositionComponents)
	{
		Comp->SetVariableVec2(FName("view_size"), ViewSize);
		Comp->SetVariableVec4(FName("view_T"), ViewT);
		Comp->SetVariableMatrix(FName("view_w2v"), ViewW2V);
		Comp->SetVariableMatrix(FName("view_v2c"), ViewV2C);
		Comp->SetVariableMatrix(FName("view_c2w"), ViewC2W);
	}
}

