/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package core.main;


import javafx.application.Application;
import javafx.application.Platform;
import javafx.stage.Modality;
import javafx.stage.Stage;

import java.util.Optional;

import core.app.MainWindowController;
import core.com.error.ShowAlert;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.scene.control.Alert;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.ButtonBar;
import javafx.scene.control.ButtonType;
import javafx.fxml.FXMLLoader;


public abstract class MainApplication extends Application {
	protected MainWindowController contMain;
	protected MainClass mainClass;
	private static boolean isTest=false;
	
	public static boolean isTestMode() {
		return isTest;
	}
	public static void setTestMode(boolean bl) {
		isTest = bl;
	}
	
	@Override
	public void start(Stage primaryStage) {
		System.out.println("QuantumVITAS is launching.");
//		primaryStage.setScene(new Scene(new Label("Hello World!")));
//      primaryStage.show();
		try {
			
			FXMLLoader fxmlLoader = new FXMLLoader(getClass().getClassLoader().getResource("core/mainWindow.fxml"));
			fxmlLoader.setController(contMain);
            Parent root = fxmlLoader.load();
            
			Scene scene = new Scene(root,1000,600);
			scene.getStylesheets().add(getClass().getClassLoader().getResource("core/application.css").toExternalForm());
			
			primaryStage.setScene(scene);
			primaryStage.setOnCloseRequest(e->{
				System.out.println("Exit button clicked.");
				
				Alert closeConfirmation = new Alert(Alert.AlertType.CONFIRMATION);
				closeConfirmation.setTitle("Closing QuantumVITAS...");
				
				ButtonType okButton = new ButtonType("Save all and exit", ButtonBar.ButtonData.YES);
				ButtonType noButton = new ButtonType("Just exit", ButtonBar.ButtonData.NO);
				ButtonType cancelButton = new ButtonType("Cancel", ButtonBar.ButtonData.CANCEL_CLOSE);
				
				closeConfirmation.getButtonTypes().setAll(okButton, noButton,cancelButton);
		        
		        closeConfirmation.setHeaderText("Save all when exiting?");
		        closeConfirmation.initModality(Modality.APPLICATION_MODAL);
		        closeConfirmation.initOwner(primaryStage);
		        
		        Optional<ButtonType> closeResponse = closeConfirmation.showAndWait();
		        if (okButton.equals(closeResponse.get())) {
		        	mainClass.projectManager.saveAllProjects();
		        }
		        else if (!noButton.equals(closeResponse.get())) {
		        	//if no, exit normally
		        	//if else (below), stop exiting
		            e.consume();
		            System.out.println("User aborts closing action.");
		            return;
		        }
		        
		        System.out.println("QuantumVITAS is closing.");
		        
				//close custom threads
			    if(mainClass!=null) {mainClass.jobManager.stop();}
			    if(contMain!=null) {contMain.killAllThreads();}
			    //standard closing
				Platform.exit();
				System.exit(0);
			});

			primaryStage.show();
		} catch(Exception e) {
			ShowAlert.showAlert(AlertType.ERROR, "Error", "Error loading the main window. Exception: "+e.getMessage());
			e.printStackTrace();
			Platform.exit();
			System.exit(0);
		}
	}
//	public static void main(String[] args) {
//        launch(args);
//    }
}
