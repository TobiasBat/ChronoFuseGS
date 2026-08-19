// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "ReadPlyFile.h"
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraComponent.h"
#include "NiagaraDataInterfaceArrayFunctionLibrary.h"
#include "DisasterData.h"
#include "Disaster_Color_Gradient.h"
#include "SplattingActor.generated.h"

class FJSONObject;

UCLASS()
class DISASTER_SPLATTING_API ASplattingActor : public AActor
{
	GENERATED_BODY()
	
public:	
	// Sets default values for this actor's properties
	ASplattingActor();
	
protected:
	// Called when the game starts or when spawned
	virtual void BeginPlay() override;
	
	UPROPERTY(EditAnywhere, Category="GSP", meta=(UIMin="0.0", UIMax="1.0", ClampMin="0.0", ClampMax="1.0", Delta="0.1"))
	TArray<float> ActivationSelection; 
	
	UPROPERTY(EditAnywhere, Category="GSP")
	int32 RenderMode; 
	
	UPROPERTY(EditAnywhere, Category="Change Vis")
	UDisaster_Color_Gradient* ChangeGradient;

	UPROPERTY(EditAnywhere, Category="Change Vis")
	bool RenderMaxOpacity; 
	
	UPROPERTY(EditAnywhere, Category="Change Vis", meta=(UIMin="1.0", UIMax="10.0", ClampMin="1.0", ClampMax="10.0", Delta="0.1"))
	float ChangeK;

	UPROPERTY(EditAnywhere, Category="Change Vis", meta=(UIMin="0.0", UIMax="0.5", ClampMin="0.0", ClampMax="0.5"))
	float ChangeB;
	
	UPROPERTY(EditAnywhere, Category="Change Vis", meta=(UIMin="0.0", UIMax="2.0", ClampMin="0.0", ClampMax="2.0"))
	float ChangeColorContrast; 

	UPROPERTY(EditAnywhere, Category="Change Vis", meta=(UIMin="0.0", UIMax="1.0", ClampMin="0.0", ClampMax="1.0"))
	float ChangeColorSaturation;

	UPROPERTY(EditAnywhere, Category="Change Vis", meta=(UIMin="0.0", UIMax="1.0", ClampMin="0.0", ClampMax="1.0"))
	float ChangeColorBrightness;
	
	UPROPERTY(EditAnywhere, Category = "GSP")
	UNiagaraSystem* NiagaraSystem;

	UPROPERTY(EditAnywhere, Category = "GSP")
	UNiagaraSystem* PositionNiagaraSystem;
	
	UPROPERTY(EditAnywhere, Category = "GSP", meta=(RequiredInput=true))
	FDirectoryPath ModelFolderPath; 
	
	UPROPERTY(EditAnywhere, Category = "GSP")
	bool UseActivationFile;
	
	// UPROPERTY(EditAnywhere, Category="GSP")
	int32 MaxNumberSplats;
	
	// UPROPERTY(EditAnywhere, Category="GSP")
	int32 MaxNumberNiagaraComponents;

	UPROPERTY(EditAnywhere, Category="GSP")
	bool VR;
	
	UPROPERTY(EditAnywhere, Category="GSP")
	int ShDegree = 0;

	UPROPERTY(EditAnywhere, Category="File Settings")
	float ColorActMult;

	UPROPERTY(EditAnywhere, Category="File Settings")
	float ColorActShift;

	UPROPERTY(EditAnywhere, Category="File Settings")
	float Scale;

	UPROPERTY(EditAnywhere, Category="GSP")
	bool AlignModelToCenter = true; 

	UPROPERTY(EditAnywhere,BlueprintReadWrite, Category="GSP")
	bool ShowCameraIndicators; 
	
	UPROPERTY(EditAnywhere, Category="GSP")
	TSubclassOf<AActor> CameraBaseActor;

	UPROPERTY(EditAnywhere, Category="GSP")
	TSubclassOf<AActor> BoundingBoxIndicatorActor;

	UPROPERTY(EditAnywhere, Category="BoundingArea")
	bool ApplyBoundingArea;

	UPROPERTY(EditAnywhere, Category="BoundingArea")
	bool BoundingAreaFromFile;
	
	UPROPERTY(EditAnywhere, Category="BoundingArea")
	TArray<FVector> UserBoundingArea;
	
	UFUNCTION(BlueprintCallable, Category="Camera")
	AActor* GetCameraActor(int index);

	UFUNCTION(BlueprintCallable, Category="Camera")
	int GetNextCameraIndex(int index, int shift); 

	UFUNCTION(BlueprintCallable, Category="Camera")
	void SetCameraIndicatorVisibility(bool Visible);

	UFUNCTION(BlueprintCallable, Category="Camera")
	float GetFieldOfView(int CameraIndex);
	
	UFUNCTION(BlueprintCallable, Category="GSP-Rendering")
	void ShowNextTimeSelection(int Shift); 

	UFUNCTION(BlueprintCallable, Category="GSP-Rendering")
	void ShowAllTimes();

	UFUNCTION(BlueprintCallable, Category="GSP-Rendering")
	void SetTimeSelection(TArray<float> Selection); 

public:
	virtual void Tick(float DeltaTime) override;

	UFUNCTION(BlueprintCallable, Category="GSP")
	void SetActivationSelection(TArray<float> Selection);

	UFUNCTION(BlueprintCallable, Category="GSP-Rendering")
	void SetRenderMode(int RenderIndex);

	UFUNCTION(BlueprintCallable, Category="GSP")
	int NumberOfTimes();

	UFUNCTION(BlueprintCallable, Category="Util")
	FText GetTimeSelectionRepresentation();

	UFUNCTION(BlueprintCallable, Category="Util")
	FText GetCameraNameFromIndex(int index);

	// Duration of each camera slot in seconds. Frame times are collected after the first
	// 10% of each slot (settle time) and every frame until the slot ends.
	// UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FPS Test")
	float FPSTestInterval = 4.0f;

	// When true, smoothly interpolates position/rotation between cameras each frame
	// instead of snapping. OnFPSTestUpdateTransform fires every tick; implement it
	// in Blueprint to move the character.
	// UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FPS Test")
	bool bFPSTestInterpolate = true;

	UFUNCTION(BlueprintCallable, Category="FPS Test")
	void StartFPSTest(int32 MaxCameras = -1);

	// Snap mode: implement in Blueprint to call SetCameraToTrainCameraIndex.
	UFUNCTION(BlueprintImplementableEvent, Category="FPS Test")
	void OnFPSTestSwitchCamera(int32 CameraIndex);

	// Interpolation mode: called every tick with the lerped transform — move the character here.
	UFUNCTION(BlueprintImplementableEvent, Category="FPS Test")
	void OnFPSTestUpdateTransform(FVector Location, FRotator Rotation);

	// Fired when all cameras have been visited.
	// AverageFPS: mean over all recorded frames.
	// OnePercentLow: average of the worst 1% of frames (key smoothness metric).
	// MinFPS: single worst frame.
	UFUNCTION(BlueprintImplementableEvent, Category="FPS Test")
	void OnFPSTestComplete(float AverageFPS, float OnePercentLow, float MinFPS);

	TArray<UNiagaraComponent*> NiagaraComponents;
	TArray<UNiagaraComponent*> NiagaraPositionComponents;

	UPROPERTY(EditAnywhere,BlueprintReadWrite, Category="GSP")
	UMaterialParameterCollection* TrueColorParameterCollection;

	UPROPERTY(EditAnywhere,BlueprintReadWrite, Category="GSP")
	UMaterialParameterCollection* DepthColorParameterCollection;

	void SetParticleFacingPosition(FVector Position);
	void SetDepthCameraMats(FVector2d ViewSize, FVector4 ViewT, FMatrix ViewW2V,  FMatrix ViewV2C, FMatrix ViewC2W); 
private:
	DisasterSplattingData Gaussians;
	FActivationData ActivationData;
	
	bool UsesActivationData;
	FVector PosTranslate;
	TArray<float> ActivationSelectionNorm; 
	TArray<FCameraData> CamerasData;
	FBoundingArea BoundingArea;

	void SetAttributes();
	void PrintHeader();
	void AlignToCenter();
	void SpawnCameraIndicators();
	void SpawnBoundingBoxIndicator();
	void UpdateActivationSelectionNiagara();
	void UpdateNormActivation();
	void UpdateChangeVisParameters();
	void UpdateBoundingArea();
	
	static TArray<FVector> SplitArray(TArray<FVector> In, const int32 FirstIndex, const int32 LastIndex);
	static TArray<FVector4> SplitArray(TArray<FVector4> In, const int32 FirstIndex, const int32 LastIndex);
	static TArray<float> SplitArray(TArray<float> In, const int32 FirstIndex, const int32 LastIndex);
	static FVector GetCenterOfPos(TArray<float> Xs, TArray<float> Ys, TArray<float> Zs);

	// FPS test state
	int32 FPSTestCameraIndex;
	int32 FPSTestCameraCount;
	TArray<float> FPSTestFrameTimes; // all recorded frame deltas across the whole test
	FTimerHandle FPSTestAdvanceTimer;
	FTimerHandle FPSTestSettleTimer;
	bool bFPSTestRunning;
	bool bFPSTestRecording; // false during the settle window at the start of each slot

	// Interpolation state
	FVector FPSTestFromPos;
	FVector FPSTestToPos;
	FQuat FPSTestFromRot;
	FQuat FPSTestToRot;
	float FPSTestSlotElapsed;

	void FPSTest_MoveToCamera();
	void FPSTest_StartRecording();
	void FPSTest_Advance();
	void FPSTest_Finish();

#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif
};
